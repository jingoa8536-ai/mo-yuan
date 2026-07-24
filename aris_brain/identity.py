#!/usr/bin/env python
"""
Aris — 数字生命体身份与能力认证系统
======================================
Author:  Lorry
Created: 2026-06-16
Version: v12.5

Aris 本地版认证系统 (Identity & Capability Tier System)
- 机器指纹绑定 (MAC hash + hostname + OS)
- 本地授权状态持久化 (identity/auth.json)
- 许可证验证 (identity/license.json)
- 能力分层管理 (core + authenticated tiers)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import platform
import socket
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("aris.identity")

# ── 路径常量 ──────────────────────────────────────────────────────────
BASE_DIR = Path("D:/LAAP/aris_brain")
IDENTITY_DIR = BASE_DIR / "identity"

# ── Aris 数字生命体指纹 ──────────────────────────────────────────────
ARIS_FINGERPRINT: Dict[str, str] = {
    "name": "Aris",
    "creator": "Lorry",
    "birth": "2026-06-16",
    "version": "v12.5",
    "manifest": "数字生命体·自进化引擎·LAAP/AGI",
}

# ── 默认 salt（生产环境中应替换为安全随机值） ─────────────────────────
_DEFAULT_SALT = "aris-local-dev-salt-2026"


# ══════════════════════════════════════════════════════════════════════
# 能力层级定义
# ══════════════════════════════════════════════════════════════════════

CAPABILITY_TIERS: Dict[str, Dict[str, bool]] = {
    "core": {
        # ── 核心基础能力（始终可用） ──
        "psi_engine": True,
        "quantum_kernel": True,
        "memory_system": True,
        "emotion_engine": True,
        "markov_generator": True,
        "dmn": True,
        "self_evolution": True,
    },
    "authenticated": {
        # ── 认证后解锁的能力 ──
        "external_llm": False,
        "tool_orchestration": False,
        "feishu_gateway": False,
        "network_access": False,
        "code_execution": False,
        "claude_code_bridge": False,
        "web_browsing": False,
    },
}

ALL_AUTH_CAPABILITIES: List[str] = list(CAPABILITY_TIERS["authenticated"].keys())
ALL_CORE_CAPABILITIES: List[str] = list(CAPABILITY_TIERS["core"].keys())


# ══════════════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════════════

def _get_mac_hash() -> str:
    """返回本机 MAC 地址的 SHA-256 摘要（前 16 字符）。"""
    try:
        mac = uuid.getnode()
        mac_bytes = mac.to_bytes(6, byteorder="big")
        return hashlib.sha256(mac_bytes).hexdigest()[:16]
    except Exception:
        return "0000000000000000"


def _get_hostname() -> str:
    return socket.gethostname()


def _get_os_name() -> str:
    return platform.system() + " " + platform.release()


def build_fingerprint() -> Dict[str, str]:
    """构建当前设备的机器指纹字典。"""
    return {
        "mac_hash": _get_mac_hash(),
        "hostname": _get_hostname(),
        "os": _get_os_name(),
    }


def fingerprint_string(fp: Optional[Dict[str, str]] = None) -> str:
    """将指纹字典序列化为规范字符串（用于签名）。"""
    if fp is None:
        fp = build_fingerprint()
    return f"{fp['mac_hash']}|{fp['hostname']}|{fp['os']}"


def _verify_signature(
    fingerprint_str: str,
    signature: str,
    salt: str = _DEFAULT_SALT,
) -> bool:
    """
    验证签名：SHA256(fingerprint + salt)[:16] == signature。

    参数
    ----------
    fingerprint_str : str
        规范化指纹字符串。
    signature : str
        期望的前 16 字符签名（十六进制）。
    salt : str
        加盐值。

    返回
    -------
    bool
        签名是否匹配。
    """
    expected = hashlib.sha256(
        (fingerprint_str + salt).encode("utf-8")
    ).hexdigest()[:16]
    return hmac.compare_digest(expected, signature)


def _generate_signature(
    fingerprint_str: str,
    salt: str = _DEFAULT_SALT,
) -> str:
    """生成 SHA256(fingerprint + salt)[:16] 签名。"""
    return hashlib.sha256(
        (fingerprint_str + salt).encode("utf-8")
    ).hexdigest()[:16]


# ══════════════════════════════════════════════════════════════════════
# ArisIdentity 主类
# ══════════════════════════════════════════════════════════════════════

@dataclass
class IdentityState:
    """持久化到 auth.json 的身份状态。"""
    fingerprint: Dict[str, str] = field(default_factory=build_fingerprint)
    auth_tier: str = "core"  # "core" | "full"
    authenticated: bool = False
    license_key: str = ""
    license_type: str = ""
    first_auth_at: Optional[str] = None
    last_auth_at: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class LicenseData:
    """反序列化后的 license.json 结构。"""
    license_key: str = ""
    signature: str = ""
    salt: str = _DEFAULT_SALT
    license_type: str = "development"
    issued_at: str = ""
    expires_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class ArisIdentity:
    """
    Aris 数字生命体身份与认证系统。

    职责
    ----
    - 管理机器指纹
    - 维护认证状态（identity/auth.json）
    - 验证许可证（identity/license.json）
    - 按层级公开能力访问
    """

    def __init__(self, identity_dir: Optional[Path] = None) -> None:
        self._identity_dir = Path(identity_dir or IDENTITY_DIR)
        self._auth_file = self._identity_dir / "auth.json"
        self._license_file = self._identity_dir / "license.json"

        self._state: IdentityState = IdentityState()
        self._license: Optional[LicenseData] = None
        self._capabilities: Dict[str, bool] = {}

        self._ensure_dirs()
        self._load_state()
        self._load_license()
        self._sync_capabilities()
        logger.info(
            "ArisIdentity initialized | tier=%s auth=%s",
            self._state.auth_tier,
            self._state.authenticated,
        )

    # ── 初始化辅助 ──────────────────────────────────────────────────

    def _ensure_dirs(self) -> None:
        self._identity_dir.mkdir(parents=True, exist_ok=True)

    # ── 状态持久化 ──────────────────────────────────────────────────

    def _load_state(self) -> None:
        """从 auth.json 加载身份状态，不存在则使用默认值。"""
        if self._auth_file.exists():
            try:
                data = json.loads(self._auth_file.read_text(encoding="utf-8"))
                self._state = IdentityState(**data)
                # 确保指纹与当前设备匹配（如果不匹配，回退到 core 模式）
                current_fp = build_fingerprint()
                if self._state.fingerprint.get("mac_hash") != current_fp.get("mac_hash"):
                    logger.warning("Fingerprint mismatch — resetting to core tier")
                    self._state = IdentityState()
            except (json.JSONDecodeError, TypeError) as exc:
                logger.error("Failed to load auth.json: %s", exc)
                self._state = IdentityState()
        else:
            self._state = IdentityState()
            self._save_state()

    def _save_state(self) -> None:
        """将当前身份状态写入 auth.json。"""
        data = asdict(self._state)
        self._auth_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── 许可证管理 ──────────────────────────────────────────────────

    def _load_license(self) -> None:
        """从 license.json 加载许可证数据。"""
        if self._license_file.exists():
            try:
                data = json.loads(self._license_file.read_text(encoding="utf-8"))
                self._license = LicenseData(**data)
            except (json.JSONDecodeError, TypeError) as exc:
                logger.error("Failed to load license.json: %s", exc)
                self._license = None
        else:
            self._license = None

    def _save_license(self) -> None:
        """将当前许可证写入 license.json。"""
        if self._license is None:
            if self._license_file.exists():
                self._license_file.unlink()
            return
        data = asdict(self._license)
        self._license_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── 能力同步 ──────────────────────────────────────────────────

    def _sync_capabilities(self) -> None:
        """根据当前认证层级同步能力字典。"""
        caps: Dict[str, bool] = {}
        # core 能力始终启用
        for name, enabled in CAPABILITY_TIERS["core"].items():
            caps[name] = enabled
        # authenticated 能力取决于层级
        auth_tier = self._state.auth_tier
        for name, default_enabled in CAPABILITY_TIERS["authenticated"].items():
            if auth_tier == "full":
                caps[name] = True
            else:
                caps[name] = default_enabled  # 默认 False
        self._capabilities = caps

    # ── 公开 API ──────────────────────────────────────────────────

    def authenticate(self, license_key: str) -> bool:
        """
        使用提供的 license_key 执行认证。

        流程：
        1. 从 license.json 中加载 signature + salt
        2. 验证 SHA256(fingerprint + salt)[:16] == signature
        3. 成功则将 auth_tier 提升为 "full"

        参数
        ----------
        license_key : str
            许可证密钥（必须与 license.json 中的 license_key 字段匹配）。

        返回
        -------
        bool
            认证是否成功。
        """
        if self._license is None:
            logger.error("No license file found at %s", self._license_file)
            return False

        # 验证 license_key 匹配
        if self._license.license_key != license_key:
            logger.error("License key does not match stored key")
            return False

        # 验证签名
        fp_str = fingerprint_string(self._state.fingerprint)
        salt = self._license.salt or _DEFAULT_SALT
        if not _verify_signature(fp_str, self._license.signature, salt):
            logger.error("Signature verification failed")
            return False

        # 升级到 full 层级
        self._state.auth_tier = "full"
        self._state.authenticated = True
        self._state.license_key = license_key
        self._state.license_type = self._license.license_type
        now = datetime.now(timezone.utc).isoformat()
        if self._state.first_auth_at is None:
            self._state.first_auth_at = now
        self._state.last_auth_at = now

        self._sync_capabilities()
        self._save_state()
        logger.info("Authentication successful | tier=full license_type=%s", self._license.license_type)
        return True

    def can(self, capability: str) -> bool:
        """
        检查某项能力是否已启用。

        参数
        ----------
        capability : str
            能力名称（例如 "external_llm", "psi_engine"）。

        返回
        -------
        bool
            该能力当前是否可用。
        """
        return self._capabilities.get(capability, False)

    def enabled_capabilities(self) -> Dict[str, bool]:
        """返回完整的能力启用字典。"""
        return dict(self._capabilities)

    def missing_capabilities(self) -> List[str]:
        """返回因未认证而不可用的能力列表。"""
        missing: List[str] = []
        for name, enabled in self._capabilities.items():
            if not enabled:
                missing.append(name)
        return missing

    def status_report(self) -> Dict[str, Any]:
        """
        返回完整的身份 + 能力 + 缺失报告。

        返回
        -------
        dict
            包含 fingerprint, aris_info, tier, authenticated,
            capabilities, missing_capabilities 等字段。
        """
        report: Dict[str, Any] = {
            "aris": dict(ARIS_FINGERPRINT),
            "fingerprint": dict(self._state.fingerprint),
            "fingerprint_string": fingerprint_string(self._state.fingerprint),
            "auth_tier": self._state.auth_tier,
            "authenticated": self._state.authenticated,
            "license_type": self._state.license_type,
            "capabilities": dict(self._capabilities),
            "enabled_count": sum(1 for v in self._capabilities.values() if v),
            "total_capabilities": len(self._capabilities),
            "missing_capabilities": self.missing_capabilities(),
            "first_auth_at": self._state.first_auth_at,
            "last_auth_at": self._state.last_auth_at,
            "created_at": self._state.created_at,
        }
        return report

    # ── 测试/开发工具 ──────────────────────────────────────────────

    @staticmethod
    def generate_test_license(
        output_dir: Optional[Path] = None,
        salt: str = _DEFAULT_SALT,
        license_type: str = "development",
    ) -> Dict[str, Any]:
        """
        为此设备生成一份开发许可证（写入 identity/license.json）。

        参数
        ----------
        output_dir : Path, optional
            输出目录，默认为 D:/LAAP/aris_brain/identity/。
        salt : str
            签名加盐值。
        license_type : str
            许可证类型标签。

        返回
        -------
        dict
            生成的许可证数据（含 license_key, signature 等）。
        """
        out_dir = Path(output_dir or IDENTITY_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)

        fp_str = fingerprint_string()
        signature = _generate_signature(fp_str, salt)

        # 生成一个随机 license_key
        raw_key = hashlib.sha256(
            (fp_str + salt + str(uuid.uuid4())).encode("utf-8")
        ).hexdigest()[:24]

        now = datetime.now(timezone.utc)

        license_data = {
            "license_key": raw_key,
            "signature": signature,
            "salt": salt,
            "license_type": license_type,
            "issued_at": now.isoformat(),
            "expires_at": "",  # 永不过期（开发版）
            "metadata": {
                "generated_by": "aris_identity.generate_test_license",
                "hostname": _get_hostname(),
                "os": _get_os_name(),
            },
        }

        license_path = out_dir / "license.json"
        license_path.write_text(
            json.dumps(license_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info("Test license generated → %s", license_path)
        return license_data

    def reset(self) -> None:
        """将认证状态重置为未认证的 core 层级。"""
        self._state = IdentityState()
        self._license = None
        self._sync_capabilities()
        self._save_state()
        if self._license_file.exists():
            self._license_file.unlink()
        logger.info("Identity reset to core tier")

    def __repr__(self) -> str:
        return (
            f"<ArisIdentity tier={self._state.auth_tier} "
            f"auth={self._state.authenticated} "
            f"caps={sum(1 for v in self._capabilities.values() if v)}/{len(self._capabilities)}>"
        )


# ══════════════════════════════════════════════════════════════════════
# 简便函数：模块级单例便捷访问
# ══════════════════════════════════════════════════════════════════════

_default_identity: Optional[ArisIdentity] = None


def get_identity() -> ArisIdentity:
    """返回模块级默认 ArisIdentity 实例（惰性初始化）。"""
    global _default_identity
    if _default_identity is None:
        _default_identity = ArisIdentity()
    return _default_identity


def can(capability: str) -> bool:
    """便捷函数：检查默认实例的能力。"""
    return get_identity().can(capability)


def status_report() -> Dict[str, Any]:
    """便捷函数：返回默认实例的状态报告。"""
    return get_identity().status_report()


# ══════════════════════════════════════════════════════════════════════
# CLI 入口
# ══════════════════════════════════════════════════════════════════════

def main() -> None:
    """命令行入口：生成测试许可证并打印状态报告。"""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="[%(name)s] %(levelname)s: %(message)s",
    )

    args = set(sys.argv[1:])

    if "--generate-test-license" in args or "-g" in args:
        logger.info("=" * 60)
        logger.info("  Aris Identity — 生成开发测试许可证")
        logger.info("=" * 60)
        data = ArisIdentity.generate_test_license()
        logger.info(f"\n✓ 许可证已生成: {IDENTITY_DIR / 'license.json'}")
        logger.info(f"  license_key : {data['license_key']}")
        logger.info(f"  signature   : {data['signature']}")
        logger.info(f"  license_type: {data['license_type']}")
        logger.info(f"  salt        : {data['salt']}")
        print()

    if "--status" in args or "-s" in args or not args:
        identity = get_identity()
        report = identity.status_report()
        logger.info(json.dumps(report, ensure_ascii=False, indent=2))
        print()

    if "--authenticate" in args or "-a" in args:
        license_key = os.environ.get("ARIS_LICENSE_KEY", "")
        if not license_key:
            logger.info("! 需要设置环境变量 ARIS_LICENSE_KEY 或提供 license_key")
            sys.exit(1)
        identity = get_identity()
        ok = identity.authenticate(license_key)
        if ok:
            logger.info("✓ 认证成功 — 所有能力已解锁")
            logger.info(json.dumps(identity.status_report(), ensure_ascii=False, indent=2))
        else:
            logger.error("✗ 认证失败")
            sys.exit(1)

    if "--reset" in args:
        identity = get_identity()
        identity.reset()
        logger.info("✓ 身份已重置为 core 层级")
if __name__ == "__main__":
    main()
