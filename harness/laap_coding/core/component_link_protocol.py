"""
LAAP Harness Component Link Protocol
====================================

组件链接协议实现，提供URI解析、哈希寻址和组件接口契约。

URI格式: harness://domain/subdomain/granularity/name@version#variant
示例:    harness://frontend/ui/atom/button@1.0.0#primary
简化:    harness://frontend/ui/atom/button

数据源: laap_harness_database.json + component_registry.py
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import jsonschema

import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "ui_web" / "core"))
from component_registry import ComponentMeta, get_registry

DATABASE_PATH = Path(__file__).parent / "laap_harness_database.json"


@dataclass(frozen=True)
class HarnessURI:
    scheme: str = "harness"
    domain: str = ""
    subdomain: str = ""
    granularity: str = ""
    name: str = ""
    version: Optional[str] = None
    variant: Optional[str] = None

    URI_PATTERN = re.compile(
        r"^harness://([^/]+)/([^/]+)/([^/]+)/([^@#]+)(?:@([^#]+))?(?:#(.+))?$"
    )

    @classmethod
    def parse(cls, uri: str) -> "HarnessURI":
        match = cls.URI_PATTERN.match(uri)
        if not match:
            raise ValueError(f"Invalid Harness URI format: {uri}")
        return cls(
            scheme="harness",
            domain=match.group(1),
            subdomain=match.group(2),
            granularity=match.group(3),
            name=match.group(4),
            version=match.group(5),
            variant=match.group(6),
        )

    def to_string(self) -> str:
        parts = [f"{self.scheme}://{self.domain}/{self.subdomain}/{self.granularity}/{self.name}"]
        if self.version:
            parts.append(f"@{self.version}")
        if self.variant:
            parts.append(f"#{self.variant}")
        return "".join(parts)

    @property
    def canonical_id(self) -> str:
        base = f"{self.domain}/{self.subdomain}/{self.granularity}/{self.name}"
        if self.version:
            base += f"@{self.version}"
        return base


class HashAddressing:
    @staticmethod
    def compute(content: Union[str, bytes]) -> str:
        if isinstance(content, str):
            content = content.encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def compute_component(component: "HarnessComponent") -> str:
        data = json.dumps(
            {
                "id": component.get_id(),
                "version": component.get_version(),
                "props_schema": component._props_schema,
                "content": component.get_content(),
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return HashAddressing.compute(data)

    @staticmethod
    def verify(content: Union[str, bytes], expected_hash: str) -> bool:
        return HashAddressing.compute(content) == expected_hash

    @staticmethod
    def verify_component(component: "HarnessComponent", expected_hash: str) -> bool:
        return HashAddressing.compute_component(component) == expected_hash


class HarnessComponent:
    def __init__(
        self,
        uri: Union[str, HarnessURI],
        metadata: Optional[Dict[str, Any]] = None,
        content: Optional[str] = None,
    ):
        if isinstance(uri, str):
            self._uri = HarnessURI.parse(uri)
        else:
            self._uri = uri
        self._metadata = metadata or {}
        self._content = content or ""
        self._props_schema = metadata.get("props_schema", {}) if metadata else {}
        self._hash_cache: Optional[str] = None

    def get_id(self) -> str:
        return self._uri.canonical_id

    def get_version(self) -> str:
        return self._uri.version or "latest"

    def validate_props(self, props: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not self._props_schema:
            return True, None
        try:
            jsonschema.validate(instance=props, schema=self._props_schema)
            return True, None
        except jsonschema.ValidationError as e:
            return False, str(e)

    def render(self, props: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
        is_valid, error = self.validate_props(props)
        if not is_valid:
            raise ValueError(f"Props validation failed: {error}")
        if self._content:
            return self._content.format(**props, **(context or {}))
        return self._generate_default_content(props, context)

    def migrate(self, from_version: str, props: Dict[str, Any]) -> Dict[str, Any]:
        if from_version == self.get_version():
            return props
        return self._apply_migration_rules(from_version, props)

    def get_content(self) -> str:
        return self._content

    def compute_hash(self) -> str:
        if self._hash_cache is None:
            self._hash_cache = HashAddressing.compute_component(self)
        return self._hash_cache

    def _generate_default_content(self, props: Dict[str, Any], context: Optional[Dict[str, Any]]) -> str:
        variant = self._uri.variant or "default"
        return f"// {self.get_id()} #{variant}\n// Props: {json.dumps(props)}\n// Context: {json.dumps(context or {})}"

    def _apply_migration_rules(self, from_version: str, props: Dict[str, Any]) -> Dict[str, Any]:
        return props


class DatabaseLoader:
    _instance: Optional["DatabaseLoader"] = None
    _data: Optional[Dict[str, Any]] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self) -> Dict[str, Any]:
        if self._data is None:
            with open(DATABASE_PATH, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        return self._data


def parse_uri(uri: str) -> HarnessURI:
    return HarnessURI.parse(uri)


def resolve_component(uri: Union[str, HarnessURI]) -> Optional[HarnessComponent]:
    if isinstance(uri, str):
        uri = HarnessURI.parse(uri)

    registry = get_registry()
    component_id = f"{uri.name}"
    if uri.variant:
        component_id = f"{uri.name}_{uri.variant}"

    meta = registry.find(component_id)
    if not meta:
        meta = registry.find(uri.name)

    if meta:
        return HarnessComponent(
            uri=uri,
            metadata={
                "id": meta.id,
                "name": meta.name,
                "category": meta.category,
                "description": meta.description,
                "tags": meta.tags,
                "variants": meta.variants,
                "dependencies": meta.dependencies,
                "props_schema": meta.props_schema,
                "quality_score": meta.quality_score,
            },
        )

    database = DatabaseLoader().load()
    if uri.domain == "frontend" and uri.subdomain == "ui":
        ui_libraries = database.get("ui_libraries", {})
        for lib_id, lib_data in ui_libraries.items():
            components = lib_data.get("components", [])
            if uri.name in components:
                return HarnessComponent(
                    uri=uri,
                    metadata={
                        "library_id": lib_id,
                        "library_name": lib_data.get("name", ""),
                        "components": components,
                        "tags": lib_data.get("tags", []),
                        "domain": lib_data.get("domain", []),
                    },
                )

    return None


def compute_hash(component: HarnessComponent) -> str:
    return component.compute_hash()


def validate_uri(uri: str) -> bool:
    try:
        HarnessURI.parse(uri)
        return True
    except ValueError:
        return False


def get_component_by_hash(component_hash: str, components: Dict[str, HarnessComponent]) -> Optional[HarnessComponent]:
    for comp in components.values():
        if comp.compute_hash() == component_hash:
            return comp
    return None
