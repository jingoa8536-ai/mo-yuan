import json
import os
import re
from typing import Dict, List, Optional, Tuple, Any


class IconRegistry:
    _instance = None
    _icons: Dict[str, str] = {}
    _categories: Dict[str, Dict[str, Any]] = {}
    _icon_metadata: Dict[str, Dict[str, List[str]]] = {}
    _index_loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IconRegistry, cls).__new__(cls)
        return cls._instance

    def _load_index(self):
        if self._index_loaded:
            return

        icons_dir = os.path.dirname(os.path.abspath(__file__))
        index_path = os.path.join(icons_dir, "index.json")

        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                index_data = json.load(f)
                self._categories = index_data.get("categories", {})
                self._icon_metadata = index_data.get("icon_metadata", {})

        category_files = {
            "user": "user.json",
            "layout": "layout.json",
            "text": "text.json",
            "map": "map.json",
            "finance": "finance.json",
            "shapes": "shapes.json",
            "accessibility": "accessibility.json",
            "social": "social.json",
            "action": "action.json",
            "communication": "communication.json",
            "files": "files.json",
            "media": "media.json",
            "navigation": "navigation.json",
            "system": "system.json"
        }

        for category, filename in category_files.items():
            filepath = os.path.join(icons_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    icons = json.load(f)
                    self._icons.update(icons)

        self._index_loaded = True

    def get_icon(self, name: str) -> Optional[str]:
        self._load_index()
        return self._icons.get(name)

    def get_category_icons(self, category: str) -> List[str]:
        self._load_index()
        category_data = self._categories.get(category)
        if category_data:
            return category_data.get("icons", [])
        return []

    def get_all_categories(self) -> List[Dict[str, Any]]:
        self._load_index()
        return [
            {"id": cat_id, "name": data["name"], "description": data["description"]}
            for cat_id, data in self._categories.items()
        ]

    def search_by_name(self, query: str) -> List[str]:
        self._load_index()
        query_lower = query.lower()
        return [
            name for name in self._icons.keys()
            if query_lower in name.lower()
        ]

    def search_by_tags(self, tags: List[str]) -> List[str]:
        self._load_index()
        result = []
        for icon_name, metadata in self._icon_metadata.items():
            icon_tags = metadata.get("tags", [])
            if any(tag.lower() in [t.lower() for t in icon_tags] for tag in tags):
                result.append(icon_name)
        return result

    def find_best_match(self, query: str) -> Optional[str]:
        self._load_index()
        query_lower = query.lower().strip()

        direct_match = self._icons.get(query_lower)
        if direct_match:
            return query_lower

        for icon_name in self._icons.keys():
            if icon_name.lower() == query_lower:
                return icon_name

        for icon_name, metadata in self._icon_metadata.items():
            aliases = metadata.get("aliases", [])
            if query_lower in [a.lower() for a in aliases]:
                return icon_name

        similar_names = self.search_by_name(query)
        if similar_names:
            return similar_names[0]

        return None

    def get_icon_svg(self, name: str, size: int = 24, stroke_width: float = 2.0) -> Optional[str]:
        self._load_index()
        svg = self._icons.get(name)
        if not svg:
            return None

        svg = svg.replace('width="24"', f'width="{size}"')
        svg = svg.replace('height="24"', f'height="{size}"')
        svg = svg.replace('stroke-width="2"', f'stroke-width="{stroke_width}"')

        return svg

    def get_icon_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        self._load_index()
        metadata = self._icon_metadata.get(name)
        if metadata:
            return metadata.copy()
        return None

    def get_icon_categories(self, name: str) -> List[str]:
        self._load_index()
        categories = []
        for cat_id, cat_data in self._categories.items():
            if name in cat_data.get("icons", []):
                categories.append(cat_id)
        return categories

    def get_all_icons(self) -> Dict[str, str]:
        self._load_index()
        return self._icons.copy()

    def get_icon_count(self) -> int:
        self._load_index()
        return len(self._icons)

    def get_category_icon_count(self, category: str) -> int:
        return len(self.get_category_icons(category))

    def generate_icon_react_component(self, name: str, size: int = 24, stroke_width: float = 2.0) -> Optional[str]:
        svg = self.get_icon_svg(name, size, stroke_width)
        if not svg:
            return None

        component_name = "".join(word.capitalize() for word in name.split("-")) + "Icon"

        return f"""import React from 'react';

export const {component_name} = ({{ className = '', style = {{}} }}: {{ className?: string; style?: React.CSSProperties }}) => (
  {svg}
);

export default {component_name};
"""

    def generate_icon_vue_component(self, name: str, size: int = 24, stroke_width: float = 2.0) -> Optional[str]:
        svg = self.get_icon_svg(name, size, stroke_width)
        if not svg:
            return None

        component_name = "".join(word.capitalize() for word in name.split("-")) + "Icon"

        return f"""<template>
  {svg}
</template>

<script setup lang="ts">
defineProps<{{
  class?: string;
}}>();
</script>
"""

    def generate_icon_html(self, name: str, size: int = 24, stroke_width: float = 2.0, color: str = "currentColor", class_name: str = "") -> Optional[str]:
        svg = self.get_icon_svg(name, size, stroke_width)
        if not svg:
            return None

        if color != "currentColor":
            svg = svg.replace('stroke="currentColor"', f'stroke="{color}"')

        if class_name:
            svg = svg.replace('<svg', f'<svg class="{class_name}"')

        return svg


registry = IconRegistry()


def get_icon(name: str) -> Optional[str]:
    return registry.get_icon(name)


def search_icons(query: str) -> List[str]:
    return registry.search_by_name(query)


def find_icon(query: str) -> Optional[str]:
    return registry.find_best_match(query)


def get_category_icons(category: str) -> List[str]:
    return registry.get_category_icons(category)


def get_all_categories() -> List[Dict[str, Any]]:
    return registry.get_all_categories()


def generate_icon_html(name: str, **kwargs) -> Optional[str]:
    return registry.generate_icon_html(name, **kwargs)
