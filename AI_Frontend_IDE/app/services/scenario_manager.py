import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List


FORMAL_PRODUCT_SCENARIOS = ("seeding",)


class ScenarioManager:
    """正式产品场景管理器：当前只开放数码购买决策主场景。"""
    def __init__(self):
        self.base_path = Path(__file__).parents[1] / "scenarios"
        self.scenarios: Dict[str, Dict[str, Any]] = {}
        self._discover_scenarios()

    def _discover_scenarios(self):
        """扫描 scenarios 目录，只加载正式产品允许的场景。"""
        if not self.base_path.exists():
            os.makedirs(self.base_path, exist_ok=True)
            return

        for scenario_dir in self.base_path.iterdir():
            if scenario_dir.is_dir() and (scenario_dir / "config.json").exists():
                name = scenario_dir.name
                if name not in FORMAL_PRODUCT_SCENARIOS:
                    continue
                with open(scenario_dir / "config.json", "r", encoding="utf-8") as f:
                    config = json.load(f)
                
                # 加载专用 Prompt
                prompt_path = scenario_dir / "prompts.xml"
                prompt_content = ""
                if prompt_path.exists():
                    with open(prompt_path, "r", encoding="utf-8") as f:
                        prompt_content = f.read()
                
                self.scenarios[name] = {
                    "config": config,
                    "prompt": prompt_content,
                    "path": scenario_dir
                }
                print(f"📦 [场景管理器] 已挂载正式场景: {name}")

    def _fallback_scenario(self) -> str:
        return "seeding" if "seeding" in self.scenarios else next(iter(self.scenarios.keys()), "")

    def get_config(self, scenario_id: str) -> Dict[str, Any]:
        """【通用配置网关】：获取场景插件的原始 JSON 配置"""
        fallback = self._fallback_scenario()
        return self.scenarios.get(scenario_id, self.scenarios.get(fallback, {})).get("config", {})

    def get_prompt(self, scenario_id: str) -> str:
        """【专属提示词网关】：获取场景插件的 prompts.xml 内容"""
        fallback = self._fallback_scenario()
        return self.scenarios.get(scenario_id, self.scenarios.get(fallback, {})).get("prompt", "")

    def get_style_mappings(self, scenario_id: str) -> Dict[str, Dict[str, str]]:
        """获取场景专属的样式翻译词典"""
        fallback = self._fallback_scenario()
        return self.scenarios.get(scenario_id, self.scenarios.get(fallback, {})).get("config", {}).get("style_mappings", {})

    def get_tools_whitelist(self, scenario_id: str) -> List[str]:
        """获取场景工具白名单"""
        fallback = self._fallback_scenario()
        return self.scenarios.get(scenario_id, self.scenarios.get(fallback, {})).get("config", {}).get("tools_whitelist", [])

    def get_contract(self, scenario_id: str) -> Dict[str, Any]:
        """获取业务原型契约"""
        fallback = self._fallback_scenario()
        return self.scenarios.get(scenario_id, self.scenarios.get(fallback, {})).get("config", {}).get("contract", {})

    def list_all_scenarios(self) -> List[str]:
        """列出当前系统内所有已安装的场景插件 ID"""
        return list(self.scenarios.keys())

# 全局单例
scenario_manager = ScenarioManager()
