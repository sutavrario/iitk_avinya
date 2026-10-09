import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
  type RulesTestEnvironment,
} from "@firebase/rules-unit-testing";
import { collection, doc, getDoc, getDocs, query, setDoc, setLogLevel, updateDoc, where } from "firebase/firestore";
import { getBytes, ref, uploadBytes } from "firebase/storage";
import { afterAll, beforeAll, beforeEach, describe, it } from "vitest";

const PROJECT_ID = "demo-vyaparai";
const BIZ_A = "bizA";
const BIZ_B = "bizB";
const ALICE = "alice"; // owner of bizA
const BOB = "bob"; // owner of bizB
const RECORD_COLLECTIONS = [
  "invoices",
  "payments",
  "customers",
  "suppliers",
  "expenses",
  "uploadedDocuments",
  "actionPlans",
  "conversations",
  "ingestionJobs",
];

let env: RulesTestEnvironment;

beforeAll(async () => {
  setLogLevel("silent"); // denied requests are expected; keep output readable
  env = await initializeTestEnvironment({
    projectId: PROJECT_ID,
    firestore: { rules: readFileSync(resolve(__dirname, "../firestore.rules"), "utf8") },
    storage: { rules: readFileSync(resolve(__dirname, "../storage.rules"), "utf8") },
  });
});

afterAll(async () => {
  await env?.cleanup();
});

beforeEach(async () => {
  await env.clearFirestore();
  await env.clearStorage();
  // Seed as the backend would (rules bypassed).
  await env.withSecurityRulesDisabled(async (ctx) => {
    const db = ctx.firestore();
    await setDoc(doc(db, "users", ALICE), { email: "alice@example.com" });
    await setDoc(doc(db, "users", BOB), { email: "bob@example.com" });
    for (const [biz, owner] of [[BIZ_A, ALICE], [BIZ_B, BOB]] as const) {
      await setDoc(doc(db, "businesses", biz), { name: biz, ownerUid: owner });
      await setDoc(doc(db, "businessMembers", `${biz}_${owner}`), { businessId: biz, uid: owner, role: "owner" });
      for (const c of RECORD_COLLECTIONS) {
        await setDoc(doc(db, c, `${c}-${biz}`), { businessId: biz, amountPaise: 100 });
      }
      await setDoc(doc(db, "conversations", `conversations-${biz}`, "messages", "m1"), { businessId: biz, text: "hi" });
      await setDoc(doc(db, "uploadedDocuments", `uploadedDocuments-${biz}`, "extractedRecords", "row00000"), { businessId: biz, run: 1 });
    }
    const storage = ctx.storage();
    await uploadBytes(ref(storage, `businesses/${BIZ_A}/documents/d1/original.csv`), new Uint8Array([1, 2, 3]));
  });
});

const as = (uid: string) => env.authenticatedContext(uid).firestore();
const anon = () => env.unauthenticatedContext().firestore();

describe("users", () => {
  it("a user can read only their own profile", async () => {
    await assertSucceeds(getDoc(doc(as(ALICE), "users", ALICE)));
    await assertFails(getDoc(doc(as(ALICE), "users", BOB)));
    await assertFails(getDoc(doc(anon(), "users", ALICE)));
  });

  it("clients cannot write user profiles, even their own", async () => {
    await assertFails(setDoc(doc(as(ALICE), "users", ALICE), { email: "x" }));
  });
});

describe("businesses & memberships", () => {
  it("members can read their business; others cannot", async () => {
    await assertSucceeds(getDoc(doc(as(ALICE), "businesses", BIZ_A)));
    await assertFails(getDoc(doc(as(ALICE), "businesses", BIZ_B)));
    await assertFails(getDoc(doc(anon(), "businesses", BIZ_A)));
  });

  it("clients cannot create businesses or grant themselves membership", async () => {
    await assertFails(setDoc(doc(as(ALICE), "businesses", "new"), { name: "x" }));
    await assertFails(
      setDoc(doc(as(ALICE), "businessMembers", `${BIZ_B}_${ALICE}`), { businessId: BIZ_B, uid: ALICE, role: "owner" }),
    );
    await assertFails(updateDoc(doc(as(ALICE), "businessMembers", `${BIZ_A}_${ALICE}`), { role: "owner" }));
  });

  it("a user can list only their own memberships", async () => {
    await assertSucceeds(getDocs(query(collection(as(ALICE), "businessMembers"), where("uid", "==", ALICE))));
    await assertFails(getDocs(query(collection(as(ALICE), "businessMembers"), where("uid", "==", BOB))));
    await assertFails(getDocs(collection(as(ALICE), "businessMembers")));
  });
});

describe("business-owned records", () => {
  for (const c of RECORD_COLLECTIONS) {
    it(`${c}: member read allowed, cross-business read denied, all client writes denied`, async () => {
      const db = as(ALICE);
      await assertSucceeds(getDoc(doc(db, c, `${c}-${BIZ_A}`)));
      await assertFails(getDoc(doc(db, c, `${c}-${BIZ_B}`)));
      await assertFails(getDoc(doc(anon(), c, `${c}-${BIZ_A}`)));
      await assertFails(setDoc(doc(db, c, "new"), { businessId: BIZ_A }));
      await assertFails(updateDoc(doc(db, c, `${c}-${BIZ_A}`), { amountPaise: 1 }));
    });
  }

  it("list queries must be scoped to a business the user belongs to", async () => {
    const db = as(ALICE);
    await assertSucceeds(getDocs(query(collection(db, "invoices"), where("businessId", "==", BIZ_A))));
    await assertFails(getDocs(query(collection(db, "invoices"), where("businessId", "==", BIZ_B))));
    await assertFails(getDocs(collection(db, "invoices")));
  });

  it("conversation messages follow the business", async () => {
    await assertSucceeds(getDoc(doc(as(ALICE), "conversations", `conversations-${BIZ_A}`, "messages", "m1")));
    await assertFails(getDoc(doc(as(ALICE), "conversations", `conversations-${BIZ_B}`, "messages", "m1")));
  });

  it("extracted draft rows follow the business and can't be edited by clients", async () => {
    const db = as(ALICE);
    const mine = doc(db, "uploadedDocuments", `uploadedDocuments-${BIZ_A}`, "extractedRecords", "row00000");
    await assertSucceeds(getDoc(mine));
    await assertFails(getDoc(doc(db, "uploadedDocuments", `uploadedDocuments-${BIZ_B}`, "extractedRecords", "row00000")));
    await assertFails(updateDoc(mine, { excluded: true }));
    await assertFails(setDoc(doc(db, "uploadedDocuments", `uploadedDocuments-${BIZ_A}`, "extractedRecords", "row99999"), { businessId: BIZ_A }));
  });

  it("unknown collections are denied", async () => {
    await assertFails(getDoc(doc(as(ALICE), "secrets", "x")));
    await assertFails(setDoc(doc(as(ALICE), "secrets", "x"), { a: 1 }));
  });
});

describe("storage", () => {
  const path = `businesses/${BIZ_A}/documents/d1/original.csv`;

  it("members can read their business's documents", async () => {
    await assertSucceeds(getBytes(ref(env.authenticatedContext(ALICE).storage(), path)));
  });

  it("non-members and anonymous users cannot read", async () => {
    await assertFails(getBytes(ref(env.authenticatedContext(BOB).storage(), path)));
    await assertFails(getBytes(ref(env.unauthenticatedContext().storage(), path)));
  });

  it("clients cannot upload, even to their own business", async () => {
    const storage = env.authenticatedContext(ALICE).storage();
    await assertFails(uploadBytes(ref(storage, `businesses/${BIZ_A}/documents/d2/x.csv`), new Uint8Array([1])));
    await assertFails(uploadBytes(ref(storage, "anything.txt"), new Uint8Array([1])));
  });
});
