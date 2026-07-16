from typing import Dict
from src.skills.base import Skill

class Agent:
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self.skills: Dict[str, Skill] = {}

    def register_skill(self, skill: Skill):
        self.skills[skill.name] = skill

    def get_skill(self, skill_name: str) -> Skill:
        if skill_name not in self.skills:
            raise ValueError(f"Agent '{self.name}' does not possess skill: '{skill_name}'")
        return self.skills[skill_name]
