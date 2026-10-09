from typing import Annotated

from fastapi import Depends
from google.cloud.firestore import Client as FirestoreClient
from google.cloud.storage import Bucket

from app.core.firebase import get_bucket, get_db

Db = Annotated[FirestoreClient, Depends(get_db)]
StorageBucket = Annotated[Bucket, Depends(get_bucket)]
