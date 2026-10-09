from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """Response models: camelCase JSON to match the frontend's TypeScript types."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class InputModel(BaseModel):
    """Request bodies: camelCase, whitespace-trimmed, and unknown fields rejected.

    `extra="forbid"` means a client cannot smuggle server-owned fields such as
    `businessId`, `createdBy` or `role` into a request.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )
