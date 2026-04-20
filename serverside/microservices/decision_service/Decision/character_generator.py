import random
from dataclasses import dataclass
from typing import Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from .models import Character as DBCharacter


@dataclass(frozen=True)
class GeneratedCharacter:
    name: str
    stamina: int
    control: int
    power: int


class MarkovAttributeChain:
    """
    Production-safe Markov chain for bounded integer states.
    """

    def __init__(
        self,
        min_state: int = 0,
        max_state: int = 10,
        rng: Optional[random.Random] = None,
    ):
        self.min_state = min_state
        self.max_state = max_state
        self.rng = rng or random.Random()
        self.transitions: Dict[int, List[int]] = {}
        self.weights: Dict[int, List[float]] = {}
        self._build_transition_model()

    def _build_transition_model(self) -> None:
        deltas = [
            (-2, 0.10),
            (-1, 0.25),
            (0, 0.30),
            (1, 0.25),
            (2, 0.10),
        ]

        for state in range(self.min_state, self.max_state + 1):
            candidates = []
            weights = []

            for delta, weight in deltas:
                next_state = state + delta
                if self.min_state <= next_state <= self.max_state:
                    candidates.append(next_state)
                    weights.append(weight)

            # normalize weights for edge states
            total = sum(weights)
            normalized = [w / total for w in weights]

            self.transitions[state] = candidates
            self.weights[state] = normalized

    def next_state(self, current_state: int) -> int:
        if current_state not in self.transitions:
            raise ValueError(f"Invalid state {current_state}")

        return self.rng.choices(
            self.transitions[current_state],
            weights=self.weights[current_state],
            k=1,
        )[0]


class CharacterGenerator:
    DEFAULT_NAMES = [
        "Tjoli",
        "Matala",
        "Sir",
        "Ngaka",
        "Ramahlale",
    ]

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        self.chain = MarkovAttributeChain(rng=self.rng)

    def _evolve(self, value: int, steps: int = 3) -> int:
        for _ in range(steps):
            value = self.chain.next_state(value)
        return value

    def _generate_attributes(self) -> Dict[str, int]:
        stamina = self._evolve(self.rng.randint(0, 10))
        control = self._evolve(self.rng.randint(0, 10))
        power = self._evolve(self.rng.randint(0, 10))

        return {
            "stamina": stamina,
            "control": control,
            "power": power,
        }

    def _unique_name(self, base_name: str) -> str:
        """
        Ensure uniqueness at DB level.
        """
        name = base_name
        counter = 1

        while DBCharacter.objects.filter(name=name).exists():
            name = f"{base_name}_{counter}"
            counter += 1

        return name

    def generate(self, count: int = 5) -> List[GeneratedCharacter]:
        names = self.DEFAULT_NAMES.copy()
        self.rng.shuffle(names)

        characters = []

        for i in range(count):
            base_name = names[i] if i < len(names) else f"Agent{i+1}"
            name = self._unique_name(base_name)
            attrs = self._generate_attributes()

            characters.append(
                GeneratedCharacter(
                    name=name,
                    stamina=attrs["stamina"],
                    control=attrs["control"],
                    power=attrs["power"],
                )
            )

        return characters

    @transaction.atomic
    def create_in_db(self, count: int = 5) -> List[DBCharacter]:
        """
        Production-safe DB creation.
        Atomic transaction prevents partial saves.
        """
        generated = self.generate(count)

        db_objects = [
            DBCharacter(
                name=char.name,
                stamina=char.stamina,
                control=char.control,
                power=char.power,
                created_at=timezone.now(),
            )
            for char in generated
        ]

        return DBCharacter.objects.bulk_create(db_objects)