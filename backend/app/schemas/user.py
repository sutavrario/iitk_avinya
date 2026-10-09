from typing import Literal

from app.schemas.business import LanguageCode, RoleName
from app.schemas.common import ApiModel, InputModel


class UserPreferences(InputModel):
    interface_language: LanguageCode = "en"
    copilot_language: LanguageCode = "en"
    always_translate_replies: bool = False
    show_original_alongside_translation: bool = True
    number_format: Literal["indian", "international"] = "indian"


class UserOut(ApiModel):
    uid: str
    email: str | None
    display_name: str | None
    email_verified: bool
    default_business_id: str | None
    preferences: UserPreferences


class MembershipOut(ApiModel):
    business_id: str
    business_name: str
    role: RoleName


class MeResponse(ApiModel):
    user: UserOut
    memberships: list[MembershipOut]
