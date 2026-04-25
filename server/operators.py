from typing import Literal

from pydantic import BaseModel

from .schemas import Region

Role = Literal["senior", "junior"]


class Operator(BaseModel):
    id: str
    name: str
    role: Role
    regions: list[Region]            # [] for senior = all regions
    avatarSeed: str

    @property
    def has_global_scope(self) -> bool:
        return self.role == "senior" or len(self.regions) == 0


OPERATORS: list[Operator] = [
    Operator(
        id="op-sarah",
        name="Sarah Lensman",
        role="senior",
        regions=[],
        avatarSeed="sarah",
    ),
    Operator(
        id="op-tarek",
        name="Tarek Bahir",
        role="junior",
        regions=["IRQ_MOSUL"],
        avatarSeed="tarek",
    ),
    Operator(
        id="op-leila",
        name="Leila Saad",
        role="junior",
        regions=["SYR_ALEPPO"],
        avatarSeed="leila",
    ),
]


def get(operator_id: str | None) -> Operator:
    for op in OPERATORS:
        if op.id == operator_id:
            return op
    return OPERATORS[0]  # default = senior


def can_act_in_region(op: Operator, region: Region | None) -> bool:
    if op.has_global_scope:
        return True
    if region is None:
        return False
    return region in op.regions


def can_broadcast_to_civilians(op: Operator) -> bool:
    """Junior operators cannot broadcast to civilian masses — only senior can."""
    return op.role == "senior"
