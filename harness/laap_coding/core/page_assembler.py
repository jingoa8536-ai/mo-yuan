import json
import os
import re
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

THEME_PRESETS = {
    "dark_flagship": {
        "name": "Dark Flagship",
        "mode": "dark",
        "tokens": {
            "--bg-primary": "#0f172a",
            "--bg-secondary": "#1e293b",
            "--bg-tertiary": "#334155",
            "--bg-card": "rgba(255, 255, 255, 0.05)",
            "--bg-hover": "rgba(255, 255, 255, 0.1)",
            "--text-primary": "#ffffff",
            "--text-secondary": "#94a3b8",
            "--text-muted": "#64748b",
            "--accent-primary": "#6366f1",
            "--accent-secondary": "#a855f7",
            "--accent-gradient": "linear-gradient(135deg, #6366f1, #a855f7)",
            "--border-color": "rgba(255, 255, 255, 0.1)",
            "--border-hover": "rgba(99, 102, 241, 0.5)",
            "--shadow-color": "rgba(99, 102, 241, 0.3)",
            "--shadow-hover": "rgba(99, 102, 241, 0.4)",
            "--font-family": "Inter, system-ui, sans-serif",
            "--radius-sm": "0.375rem",
            "--radius-md": "0.5rem",
            "--radius-lg": "0.75rem",
            "--radius-xl": "1rem",
            "--radius-2xl": "1.5rem",
        }
    },
    "minimal_white": {
        "name": "Minimal White",
        "mode": "light",
        "tokens": {
            "--bg-primary": "#ffffff",
            "--bg-secondary": "#f8fafc",
            "--bg-tertiary": "#f1f5f9",
            "--bg-card": "#ffffff",
            "--bg-hover": "#f1f5f9",
            "--text-primary": "#1e293b",
            "--text-secondary": "#64748b",
            "--text-muted": "#94a3b8",
            "--accent-primary": "#3b82f6",
            "--accent-secondary": "#0ea5e9",
            "--accent-gradient": "linear-gradient(135deg, #3b82f6, #0ea5e9)",
            "--border-color": "#e2e8f0",
            "--border-hover": "#94a3b8",
            "--shadow-color": "rgba(0, 0, 0, 0.1)",
            "--shadow-hover": "rgba(0, 0, 0, 0.15)",
            "--font-family": "Inter, system-ui, sans-serif",
            "--radius-sm": "0.375rem",
            "--radius-md": "0.5rem",
            "--radius-lg": "0.75rem",
            "--radius-xl": "1rem",
            "--radius-2xl": "1.5rem",
        }
    },
    "ocean_blue": {
        "name": "Ocean Blue",
        "mode": "dark",
        "tokens": {
            "--bg-primary": "#0c1929",
            "--bg-secondary": "#0a2463",
            "--bg-tertiary": "#1e3a5f",
            "--bg-card": "rgba(30, 58, 95, 0.5)",
            "--bg-hover": "rgba(30, 58, 95, 0.7)",
            "--text-primary": "#ffffff",
            "--text-secondary": "#7dd3fc",
            "--text-muted": "#0ea5e9",
            "--accent-primary": "#06b6d4",
            "--accent-secondary": "#38bdf8",
            "--accent-gradient": "linear-gradient(135deg, #06b6d4, #38bdf8)",
            "--border-color": "rgba(6, 182, 212, 0.3)",
            "--border-hover": "rgba(6, 182, 212, 0.6)",
            "--shadow-color": "rgba(6, 182, 212, 0.3)",
            "--shadow-hover": "rgba(6, 182, 212, 0.5)",
            "--font-family": "Inter, system-ui, sans-serif",
            "--radius-sm": "0.375rem",
            "--radius-md": "0.5rem",
            "--radius-lg": "0.75rem",
            "--radius-xl": "1rem",
            "--radius-2xl": "1.5rem",
        }
    },
    "forest_green": {
        "name": "Forest Green",
        "mode": "dark",
        "tokens": {
            "--bg-primary": "#052e16",
            "--bg-secondary": "#14532d",
            "--bg-tertiary": "#166534",
            "--bg-card": "rgba(20, 83, 45, 0.5)",
            "--bg-hover": "rgba(20, 83, 45, 0.7)",
            "--text-primary": "#ffffff",
            "--text-secondary": "#bbf7d0",
            "--text-muted": "#86efac",
            "--accent-primary": "#22c55e",
            "--accent-secondary": "#4ade80",
            "--accent-gradient": "linear-gradient(135deg, #22c55e, #4ade80)",
            "--border-color": "rgba(34, 197, 94, 0.3)",
            "--border-hover": "rgba(34, 197, 94, 0.6)",
            "--shadow-color": "rgba(34, 197, 94, 0.3)",
            "--shadow-hover": "rgba(34, 197, 94, 0.5)",
            "--font-family": "Inter, system-ui, sans-serif",
            "--radius-sm": "0.375rem",
            "--radius-md": "0.5rem",
            "--radius-lg": "0.75rem",
            "--radius-xl": "1rem",
            "--radius-2xl": "1.5rem",
        }
    },
    "sunset_orange": {
        "name": "Sunset Orange",
        "mode": "light",
        "tokens": {
            "--bg-primary": "#fff7ed",
            "--bg-secondary": "#ffedd5",
            "--bg-tertiary": "#fed7aa",
            "--bg-card": "#ffffff",
            "--bg-hover": "#ffedd5",
            "--text-primary": "#431407",
            "--text-secondary": "#7c2d12",
            "--text-muted": "#9a3412",
            "--accent-primary": "#f97316",
            "--accent-secondary": "#fb923c",
            "--accent-gradient": "linear-gradient(135deg, #f97316, #fb923c)",
            "--border-color": "#fed7aa",
            "--border-hover": "#f97316",
            "--shadow-color": "rgba(249, 115, 22, 0.2)",
            "--shadow-hover": "rgba(249, 115, 22, 0.3)",
            "--font-family": "Inter, system-ui, sans-serif",
            "--radius-sm": "0.375rem",
            "--radius-md": "0.5rem",
            "--radius-lg": "0.75rem",
            "--radius-xl": "1rem",
            "--radius-2xl": "1.5rem",
        }
    },
    "midnight_purple": {
        "name": "Midnight Purple",
        "mode": "dark",
        "tokens": {
            "--bg-primary": "#1e1b4b",
            "--bg-secondary": "#312e81",
            "--bg-tertiary": "#4c1d95",
            "--bg-card": "rgba(49, 46, 129, 0.5)",
            "--bg-hover": "rgba(49, 46, 129, 0.7)",
            "--text-primary": "#ffffff",
            "--text-secondary": "#ddd6fe",
            "--text-muted": "#c4b5fd",
            "--accent-primary": "#a855f7",
            "--accent-secondary": "#d946ef",
            "--accent-gradient": "linear-gradient(135deg, #a855f7, #d946ef)",
            "--border-color": "rgba(168, 85, 247, 0.3)",
            "--border-hover": "rgba(168, 85, 247, 0.6)",
            "--shadow-color": "rgba(168, 85, 247, 0.3)",
            "--shadow-hover": "rgba(168, 85, 247, 0.5)",
            "--font-family": "Inter, system-ui, sans-serif",
            "--radius-sm": "0.375rem",
            "--radius-md": "0.5rem",
            "--radius-lg": "0.75rem",
            "--radius-xl": "1rem",
            "--radius-2xl": "1.5rem",
        }
    }
}


class DependencyResolver:
    def __init__(self, database_path: str):
        self.database = self._load_database(database_path)
        self.dependencies: Dict[str, Dict[str, Any]] = {}
        self.conflicts: List[Dict[str, Any]] = []
        self.dependency_tree: Dict[str, Any] = {}

    def _load_database(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            raise ValueError(f"Failed to load database: {e}")

    def analyze_component_dependencies(self, component_uri: str) -> Dict[str, Any]:
        category, name = self._parse_uri(component_uri)
        dependencies = {
            "uri": component_uri,
            "category": category,
            "name": name,
            "requires": [],
            "conflicts_with": []
        }

        if category == "sections":
            dependencies["requires"] = ["navbar", "hero"]
            if name in ["pricing_template_01", "features_template_01"]:
                dependencies["requires"].append("card")
            if name == "faq_template_01":
                dependencies["requires"].append("accordion")

        elif category == "molecules":
            if name.startswith("card"):
                dependencies["requires"] = ["button", "typography"]
            if name == "accordion_default":
                dependencies["requires"] = ["button"]
            if name.startswith("tabs"):
                dependencies["requires"] = ["button"]
            if name.startswith("modal"):
                dependencies["requires"] = ["button"]

        elif category == "atoms":
            if name.startswith("button"):
                dependencies["requires"] = ["typography"]
            if name.startswith("input"):
                dependencies["requires"] = ["typography"]

        return dependencies

    def _parse_uri(self, component_uri: str) -> Tuple[str, str]:
        parts = component_uri.split('/')
        if len(parts) >= 2:
            return parts[-2], parts[-1].replace('.html', '')
        return "unknown", component_uri

    def detect_version_conflicts(self, components: List[str]) -> List[Dict[str, Any]]:
        conflicts = []
        libraries_used = {}

        for comp_uri in components:
            category = self._parse_uri(comp_uri)[0]
            if category == "sections":
                libraries_used["float_ui"] = {"name": "Float UI", "version": "latest"}
                libraries_used["daisyui"] = {"name": "DaisyUI", "version": "latest"}
            elif category in ["molecules", "atoms"]:
                libraries_used["shadcn_ui"] = {"name": "shadcn/ui", "version": "latest"}

        react_libs = [k for k in libraries_used if k in ["shadcn_ui", "ant_design", "material_ui", "chakra_ui", "mantine", "radix_ui"]]
        vue_libs = [k for k in libraries_used if k in ["element_plus", "naive_ui", "shadcn_vue"]]

        if len(react_libs) > 1:
            conflicts.append({
                "type": "framework_conflict",
                "message": f"Multiple React libraries detected: {', '.join(react_libs)}",
                "libraries": react_libs,
                "suggestion": "Choose one primary React library for consistency"
            })

        if len(vue_libs) > 1:
            conflicts.append({
                "type": "framework_conflict",
                "message": f"Multiple Vue libraries detected: {', '.join(vue_libs)}",
                "libraries": vue_libs,
                "suggestion": "Choose one primary Vue library for consistency"
            })

        if react_libs and vue_libs:
            conflicts.append({
                "type": "framework_conflict",
                "message": f"Both React and Vue libraries detected: React({react_libs}), Vue({vue_libs})",
                "suggestion": "Use either React or Vue, not both"
            })

        return conflicts

    def generate_dependency_tree(self, components: List[str]) -> Dict[str, Any]:
        tree = {"root": {"components": [], "dependencies": {}}}

        for comp_uri in components:
            deps = self.analyze_component_dependencies(comp_uri)
            category, name = self._parse_uri(comp_uri)

            if category not in tree["root"]["dependencies"]:
                tree["root"]["dependencies"][category] = {"components": []}

            tree["root"]["dependencies"][category]["components"].append({
                "name": name,
                "uri": comp_uri,
                "requires": deps["requires"]
            })

            tree["root"]["components"].append({
                "name": name,
                "uri": comp_uri,
                "category": category
            })

        self.dependency_tree = tree
        return tree

    def resolve_dependencies(self, components: List[str]) -> Dict[str, Any]:
        self.conflicts = self.detect_version_conflicts(components)
        self.dependency_tree = self.generate_dependency_tree(components)

        return {
            "success": len(self.conflicts) == 0,
            "tree": self.dependency_tree,
            "conflicts": self.conflicts,
            "total_components": len(components),
            "categories": list(self.dependency_tree["root"]["dependencies"].keys())
        }


class ThemeInjector:
    def __init__(self):
        self.current_theme = None
        self.theme_css = ""

    def generate_theme_css(self, theme_name: str) -> str:
        if theme_name not in THEME_PRESETS:
            raise ValueError(f"Theme '{theme_name}' not found. Available: {list(THEME_PRESETS.keys())}")

        theme = THEME_PRESETS[theme_name]
        tokens = theme["tokens"]
        mode = theme["mode"]

        css = f":root {{\n"
        for key, value in tokens.items():
            css += f"  {key}: {value};\n"
        css += "}\n\n"

        css += f".theme-{theme_name} {{\n"
        for key, value in tokens.items():
            css += f"  {key}: {value};\n"
        css += "}\n\n"

        if mode == "dark":
            css += "@media (prefers-color-scheme: dark) {\n"
            css += "  :root {\n"
            for key, value in tokens.items():
                css += f"    {key}: {value};\n"
            css += "  }\n}\n"

        css += """
        [data-theme="dark"] {
            color-scheme: dark;
        }
        
        [data-theme="light"] {
            color-scheme: light;
        }
        """

        self.current_theme = theme_name
        self.theme_css = css
        return css

    def get_theme_tokens(self, theme_name: str) -> Dict[str, str]:
        if theme_name not in THEME_PRESETS:
            raise ValueError(f"Theme '{theme_name}' not found")
        return THEME_PRESETS[theme_name]["tokens"]

    def get_available_themes(self) -> List[str]:
        return list(THEME_PRESETS.keys())

    def generate_theme_switcher_js(self) -> str:
        themes = self.get_available_themes()
        js = f"""
        function setTheme(themeName) {{
            const themeTokens = {json.dumps(THEME_PRESETS)};
            const root = document.documentElement;
            const tokens = themeTokens[themeName].tokens;
            
            for (const [key, value] of Object.entries(tokens)) {{
                root.style.setProperty(key, value);
            }}
            
            root.setAttribute('data-theme', themeTokens[themeName].mode);
            localStorage.setItem('laap-theme', themeName);
        }}
        
        function initTheme() {{
            const savedTheme = localStorage.getItem('laap-theme') || '{list(THEME_PRESETS.keys())[0]}';
            setTheme(savedTheme);
        }}
        
        document.addEventListener('DOMContentLoaded', initTheme);
        """
        return js.strip()


class CodeGenerator:
    def __init__(self, templates_dir: str):
        self.templates_dir = Path(templates_dir)
        self.components: List[Dict[str, Any]] = []
        self.theme_injector = ThemeInjector()
        self.current_theme = None

    def load_component(self, component_uri: str, props: Dict[str, Any]) -> str:
        category, name = self._parse_uri(component_uri)
        template_path = self.templates_dir / "ui" / category / f"{name}.html"

        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return self._render_template(content, props)

    def _parse_uri(self, component_uri: str) -> Tuple[str, str]:
        parts = component_uri.split('/')
        if len(parts) >= 2:
            return parts[-2], parts[-1]
        return "unknown", component_uri

    def _render_template(self, template: str, props: Dict[str, Any]) -> str:
        content = template

        content = re.sub(r'\{\{\s*(\w+)\s*\}\}', lambda m: str(props.get(m.group(1), '')), content)

        content = re.sub(
            r'\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}',
            lambda m: self._render_loop(m.group(1), m.group(2), m.group(3), props),
            content,
            flags=re.DOTALL
        )

        return content

    def _render_loop(self, item_var: str, collection_var: str, body: str, props: Dict[str, Any]) -> str:
        collection = props.get(collection_var, [])
        result = ""
        for item in collection:
            item_body = body.replace(f"{{{{ {item_var}.", "{{").replace(f"{{{{{item_var}.", "{{")
            item_body = re.sub(r'\{\{\s*(\w+)\s*\}\}', lambda m: str(item.get(m.group(1), '')), item_body)
            result += item_body
        return result

    def generate_html(self, components: List[Dict[str, Any]], theme_name: str = "dark_flagship") -> str:
        self.components = components
        self.current_theme = theme_name

        theme_css = self.theme_injector.generate_theme_css(theme_name)
        theme_js = self.theme_injector.generate_theme_switcher_js()

        head = self._generate_head(theme_name, theme_css)
        body_content = self._generate_body_content(components)
        body = self._generate_body(body_content, theme_js)

        return f"<!DOCTYPE html>\n<html lang=\"zh-CN\">\n{head}\n{body}\n</html>"

    def _generate_head(self, theme_name: str, theme_css: str) -> str:
        theme = THEME_PRESETS[theme_name]
        return f"""<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LAAP Harness Page</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        {theme_css}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: var(--font-family);
            background-color: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            transition: all 0.3s ease;
        }}
        
        ::selection {{
            background-color: var(--accent-primary);
            color: white;
        }}
    </style>
</head>"""

    def _generate_body_content(self, components: List[Dict[str, Any]]) -> str:
        content = ""
        for comp in components:
            try:
                html = self.load_component(comp["uri"], comp.get("props", {}))
                content += html + "\n"
            except Exception as e:
                content += f"<!-- Failed to render {comp['uri']}: {e} -->\n"
        return content

    def _generate_body(self, content: str, theme_js: str) -> str:
        return f"""<body data-theme="{THEME_PRESETS[self.current_theme]['mode']}">
    {content}
    
    <script>
        {theme_js}
        
        document.addEventListener('DOMContentLoaded', function() {{
            document.querySelectorAll('.accordion-header').forEach(header => {{
                header.addEventListener('click', function() {{
                    const content = this.nextElementSibling;
                    const icon = this.querySelector('.accordion-icon');
                    
                    content.style.display = content.style.display === 'none' ? 'block' : 'none';
                    icon.style.transform = icon.style.transform === 'rotate(180deg)' ? 'rotate(0deg)' : 'rotate(180deg)';
                }});
            }});
            
            document.querySelectorAll('.accordion-content').forEach(content => {{
                content.style.display = 'none';
            }});
        }});
    </script>
</body>"""


class PageAssembler:
    def __init__(self, templates_dir: str, database_path: str):
        self.templates_dir = templates_dir
        self.database_path = database_path
        self.components: List[Dict[str, Any]] = []
        self.dependency_resolver = DependencyResolver(database_path)
        self.code_generator = CodeGenerator(templates_dir)
        self.theme_injector = ThemeInjector()
        self.current_theme = None

    def add_component(self, component_uri: str, props: Optional[Dict[str, Any]] = None) -> None:
        if props is None:
            props = {}

        self.components.append({
            "uri": component_uri,
            "props": props
        })

    def resolve_dependencies(self) -> Dict[str, Any]:
        component_uris = [comp["uri"] for comp in self.components]
        return self.dependency_resolver.resolve_dependencies(component_uris)

    def generate_html(self) -> str:
        if not self.current_theme:
            self.current_theme = "dark_flagship"

        return self.code_generator.generate_html(self.components, self.current_theme)

    def inject_theme(self, theme_name: str) -> None:
        if theme_name not in THEME_PRESETS:
            raise ValueError(f"Theme '{theme_name}' not found. Available: {list(THEME_PRESETS.keys())}")
        self.current_theme = theme_name

    def get_available_themes(self) -> List[str]:
        return self.theme_injector.get_available_themes()

    def get_component_list(self) -> List[Dict[str, Any]]:
        return self.components

    def clear_components(self) -> None:
        self.components = []

    def validate_components(self) -> Dict[str, Any]:
        errors = []
        warnings = []

        for comp in self.components:
            category, name = self._parse_uri(comp["uri"])
            template_path = Path(self.templates_dir) / "ui" / category / f"{name}.html"

            if not template_path.exists():
                errors.append({
                    "component": comp["uri"],
                    "error": "Template not found",
                    "path": str(template_path)
                })

            required_props = self._get_required_props(category, name)
            missing_props = [prop for prop in required_props if prop not in comp["props"]]

            if missing_props:
                warnings.append({
                    "component": comp["uri"],
                    "warning": "Missing required props",
                    "missing": missing_props
                })

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "total_components": len(self.components)
        }

    def _parse_uri(self, component_uri: str) -> Tuple[str, str]:
        parts = component_uri.split('/')
        if len(parts) >= 2:
            return parts[-2], parts[-1]
        return "unknown", component_uri

    def _get_required_props(self, category: str, name: str) -> List[str]:
        required_props = {
            "sections": {
                "hero_template_01": ["badge", "title", "description", "primary_cta", "secondary_cta", "stats"],
                "navbar_template_01": ["logo", "brand", "links"],
                "features_template_01": ["title", "description", "features"],
                "pricing_template_01": ["title", "description", "plans"],
                "faq_template_01": ["title", "items"],
                "cta_template_01": ["title", "description", "cta_text"]
            },
            "molecules": {
                "card_default": ["icon", "title", "description"],
                "card_glass": ["icon", "title", "description"],
                "card_pricing": ["name", "price", "features", "cta"],
                "accordion_default": ["items"],
                "tabs_underline": ["tabs"],
                "modal_center": ["title", "content"]
            },
            "atoms": {
                "button_primary": ["label"],
                "button_secondary": ["label"],
                "button_outline": ["label"],
                "button_ghost": ["label"],
                "button_glass": ["label"],
                "button_danger": ["label"],
                "input_text": ["placeholder"],
                "input_search": ["placeholder"],
                "typography_h1": ["text"],
                "typography_h2": ["text"],
                "typography_body": ["text"],
                "badge_default": ["text"],
                "badge_success": ["text"],
                "badge_warning": ["text"],
                "badge_error": ["text"]
            }
        }

        return required_props.get(category, {}).get(name, [])