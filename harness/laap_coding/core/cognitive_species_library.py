"""
Cognitive Species Library — 认知物种库
=========================================
让编译产物自动成为新的组件/技能/能力

核心理念:
  - 每次编译的产物本身可以成为一个新的组件/技能/能力
  - Harness会自我生长 — 每用一次，就多一个模板
  - 支持三种形态: Component(组件), Skill(技能), Ability(能力)

数据模型:
  Species = {
    id: str,
    name: str,
    type: "component" | "skill" | "ability",
    origin: "compiled" | "imported" | "evolved",
    template: str,
    props: Dict[str, Any],
    dependencies: List[str],
    success_rate: float,
    usage_count: int,
    quality_score: float,
    tags: List[str],
    domain: List[str],
    created_at: float,
    last_used: float,
  }

实现三个方向:
  1. 从 "代码库" 到 "认知物种库"
  2. 编译产物自动注册为新物种
  3. 物种进化和淘汰机制
"""

from __future__ import annotations

import os
import json
import time
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = __import__('logging').getLogger("laap.cognitive_species")


class SpeciesType(Enum):
    COMPONENT = "component"
    SKILL = "skill"
    ABILITY = "ability"


class SpeciesOrigin(Enum):
    COMPILED = "compiled"
    IMPORTED = "imported"
    EVOLVED = "evolved"


@dataclass
class Species:
    id: str
    name: str
    type: SpeciesType
    origin: SpeciesOrigin
    template: str
    props: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    success_rate: float = 1.0
    usage_count: int = 0
    quality_score: float = 0.0
    tags: List[str] = field(default_factory=list)
    domain: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "origin": self.origin.value,
            "template": self.template,
            "props": self.props,
            "dependencies": self.dependencies,
            "success_rate": self.success_rate,
            "usage_count": self.usage_count,
            "quality_score": self.quality_score,
            "tags": self.tags,
            "domain": self.domain,
            "created_at": self.created_at,
            "last_used": self.last_used,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Species:
        return cls(
            id=data["id"],
            name=data["name"],
            type=SpeciesType(data["type"]),
            origin=SpeciesOrigin(data["origin"]),
            template=data["template"],
            props=data.get("props", {}),
            dependencies=data.get("dependencies", []),
            success_rate=data.get("success_rate", 1.0),
            usage_count=data.get("usage_count", 0),
            quality_score=data.get("quality_score", 0.0),
            tags=data.get("tags", []),
            domain=data.get("domain", []),
            created_at=data.get("created_at", time.time()),
            last_used=data.get("last_used", time.time()),
        )

    def update_usage(self, success: bool, quality_score: float = None):
        self.usage_count += 1
        self.last_used = time.time()
        if quality_score is not None:
            self.quality_score = (self.quality_score * (self.usage_count - 1) + quality_score) / self.usage_count
        if success:
            self.success_rate = min(1.0, (self.success_rate * (self.usage_count - 1) + 1.0) / self.usage_count)
        else:
            self.success_rate = max(0.0, (self.success_rate * (self.usage_count - 1) + 0.0) / self.usage_count)


class CognitiveSpeciesLibrary:
    """认知物种库：管理所有编译产物，实现自我生长"""

    SPECIES_FILE = "cognitive_species.json"

    def __init__(self, project_root: str = ""):
        self.project_root = project_root or os.getcwd()
        self._species: Dict[str, Species] = {}
        self._type_index: Dict[str, List[str]] = {}
        self._tag_index: Dict[str, List[str]] = {}
        self._domain_index: Dict[str, List[str]] = {}
        self._load_species()

    def _load_species(self):
        species_path = os.path.join(self.project_root, self.SPECIES_FILE)
        if os.path.exists(species_path):
            try:
                with open(species_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for species_data in data.get("species", []):
                        species = Species.from_dict(species_data)
                        self._species[species.id] = species
                        self._update_indexes(species)
                logger.info(f"[CognitiveSpeciesLibrary] Loaded {len(self._species)} species")
            except Exception as e:
                logger.warning(f"[CognitiveSpeciesLibrary] Failed to load species: {e}")

    def _save_species(self):
        species_path = os.path.join(self.project_root, self.SPECIES_FILE)
        try:
            data = {
                "version": "1.0",
                "total": len(self._species),
                "species": [s.to_dict() for s in self._species.values()],
            }
            with open(species_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"[CognitiveSpeciesLibrary] Failed to save species: {e}")

    def _update_indexes(self, species: Species):
        type_key = species.type.value
        if type_key not in self._type_index:
            self._type_index[type_key] = []
        if species.id not in self._type_index[type_key]:
            self._type_index[type_key].append(species.id)

        for tag in species.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = []
            if species.id not in self._tag_index[tag]:
                self._tag_index[tag].append(species.id)

        for domain in species.domain:
            if domain not in self._domain_index:
                self._domain_index[domain] = []
            if species.id not in self._domain_index[domain]:
                self._domain_index[domain].append(species.id)

    def _generate_species_id(self, template: str, props: Dict[str, Any], versioned: bool = True) -> str:
        base_content = f"{template}:{json.dumps(props, sort_keys=True)}"
        base_hash = hashlib.md5(base_content.encode()).hexdigest()[:12]
        
        if versioned:
            timestamp = str(int(time.time()))[-6:]
            import random
            variant = random.randint(0, 999)
            return f"{base_hash}_{timestamp}_{variant:03d}"
        return base_hash

    def register_compiled_species(self, template: str, props: Dict[str, Any],
                                  tags: List[str] = None, domain: List[str] = None) -> Species:
        species_id = self._generate_species_id(template, props)
        if species_id in self._species:
            species = self._species[species_id]
            species.usage_count += 1
            species.last_used = time.time()
            logger.info(f"[CognitiveSpeciesLibrary] Updated existing species: {species.name}")
        else:
            base_id = self._generate_species_id(template, props, versioned=False)
            existing_variants = [s for s in self._species.values() if s.id.startswith(base_id)]
            
            if existing_variants:
                variant_count = len(existing_variants)
                species_name = f"{template}_{base_id[:8]}_v{variant_count}"
            else:
                species_name = f"{template}_{species_id[:8]}"
            
            species = Species(
                id=species_id,
                name=species_name,
                type=self._infer_type(template),
                origin=SpeciesOrigin.COMPILED,
                template=template,
                props=props,
                tags=tags or [],
                domain=domain or [],
            )
            self._species[species_id] = species
            self._update_indexes(species)
            logger.info(f"[CognitiveSpeciesLibrary] Registered new species: {species_name} (variant #{len([s for s in self._species.values() if s.id.startswith(base_id)])})")

        self._save_species()
        return species

    def _infer_type(self, template: str) -> SpeciesType:
        component_keywords = ["button", "card", "modal", "input", "table", "form", "dialog"]
        skill_keywords = ["function", "api", "tool", "service", "task"]
        if any(kw in template.lower() for kw in component_keywords):
            return SpeciesType.COMPONENT
        elif any(kw in template.lower() for kw in skill_keywords):
            return SpeciesType.SKILL
        else:
            return SpeciesType.ABILITY

    def get_species(self, species_id: str) -> Optional[Species]:
        return self._species.get(species_id)

    def list_species(self, type_filter: Optional[str] = None,
                     tag_filter: Optional[str] = None,
                     domain_filter: Optional[str] = None) -> List[Species]:
        filtered = list(self._species.values())

        if type_filter:
            filtered = [s for s in filtered if s.type.value == type_filter]

        if tag_filter:
            filtered = [s for s in filtered if tag_filter in s.tags]

        if domain_filter:
            filtered = [s for s in filtered if domain_filter in s.domain]

        return sorted(filtered, key=lambda s: (-s.usage_count, -s.quality_score))

    def search_species(self, query: str) -> List[Species]:
        query_terms = [t.lower() for t in query.split() if t.strip()]
        if not query_terms:
            return []

        results = []
        for species in self._species.values():
            score = 0
            species_name_lower = species.name.lower()
            species_template_lower = species.template.lower()
            
            for term in query_terms:
                if term in species_name_lower:
                    score += 3
                if term in species_template_lower:
                    score += 2
                if any(term in tag.lower() for tag in species.tags):
                    score += 1
                if any(term in d.lower() for d in species.domain):
                    score += 1
                for prop_key, prop_value in species.props.items():
                    if term in str(prop_key).lower():
                        score += 1
                    if term in str(prop_value).lower():
                        score += 1
            if score > 0:
                results.append((species, score))

        return [s for s, _ in sorted(results, key=lambda x: -x[1])]

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._species)
        by_type = {t.value: len(self._type_index.get(t.value, [])) for t in SpeciesType}
        by_origin = {}
        for species in self._species.values():
            key = species.origin.value
            by_origin[key] = by_origin.get(key, 0) + 1

        avg_usage = sum(s.usage_count for s in self._species.values()) / max(total, 1)
        avg_success = sum(s.success_rate for s in self._species.values()) / max(total, 1)

        return {
            "total_species": total,
            "by_type": by_type,
            "by_origin": by_origin,
            "avg_usage": round(avg_usage, 2),
            "avg_success_rate": round(avg_success, 4),
            "top_species": [s.to_dict() for s in self.list_species()[:5]],
        }

    def evolve_species(self, species_id: str, new_template: str,
                       new_props: Dict[str, Any]) -> Species:
        old_species = self._species.get(species_id)
        if not old_species:
            raise ValueError(f"Species {species_id} not found")

        new_id = self._generate_species_id(new_template, new_props)
        if new_id == species_id:
            return old_species

        evolved = Species(
            id=new_id,
            name=f"evolved_{old_species.name}",
            type=old_species.type,
            origin=SpeciesOrigin.EVOLVED,
            template=new_template,
            props=new_props,
            dependencies=[species_id],
            success_rate=old_species.success_rate,
            usage_count=0,
            quality_score=old_species.quality_score,
            tags=old_species.tags + ["evolved"],
            domain=old_species.domain,
        )

        self._species[new_id] = evolved
        self._update_indexes(evolved)
        self._save_species()
        logger.info(f"[CognitiveSpeciesLibrary] Species evolved: {old_species.name} → {evolved.name}")
        return evolved

    def prune_species(self, min_usage: int = 0, max_age_days: int = None) -> int:
        pruned_count = 0
        now = time.time()
        to_remove = []

        for species_id, species in self._species.items():
            if species.usage_count < min_usage:
                to_remove.append(species_id)
            elif max_age_days and (now - species.created_at) > max_age_days * 86400:
                to_remove.append(species_id)

        for species_id in to_remove:
            species = self._species.pop(species_id)
            self._clean_indexes(species)
            pruned_count += 1
            logger.info(f"[CognitiveSpeciesLibrary] Pruned species: {species.name}")

        if pruned_count > 0:
            self._save_species()

        return pruned_count

    def _clean_indexes(self, species: Species):
        for index in [self._type_index, self._tag_index, self._domain_index]:
            for key, ids in list(index.items()):
                if species.id in ids:
                    ids.remove(species.id)
                    if not ids:
                        del index[key]

    def merge_species(self, species_ids: List[str]) -> Optional[Species]:
        if len(species_ids) < 2:
            return None

        sources = [self._species.get(sid) for sid in species_ids if self._species.get(sid)]
        if len(sources) < 2:
            return None

        merged_props = {}
        merged_tags = set()
        merged_domain = set()
        for s in sources:
            merged_props.update(s.props)
            merged_tags.update(s.tags)
            merged_domain.update(s.domain)

        merged_template = "+".join(s.template for s in sources)
        merged_id = self._generate_species_id(merged_template, merged_props)

        if merged_id in self._species:
            return self._species[merged_id]

        merged = Species(
            id=merged_id,
            name=f"merged_{merged_id[:8]}",
            type=sources[0].type,
            origin=SpeciesOrigin.EVOLVED,
            template=merged_template,
            props=merged_props,
            dependencies=species_ids,
            success_rate=sum(s.success_rate for s in sources) / len(sources),
            usage_count=0,
            quality_score=sum(s.quality_score for s in sources) / len(sources),
            tags=list(merged_tags) + ["merged"],
            domain=list(merged_domain),
        )

        self._species[merged_id] = merged
        self._update_indexes(merged)
        self._save_species()
        logger.info(f"[CognitiveSpeciesLibrary] Merged {len(sources)} species into: {merged.name}")
        return merged
