import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

class ScenarioManager:
    """
    【X-Forge 3.0 场景调度员】：负责动态加载和管理不同赛道的插件配置与提示词。
    """
    def __init__(self):
        self.base_path = Path(__file__).parents[1] / "scenarios"
        self.scenarios: Dict[str, Dict[str, Any]] = {}
        self._discover_scenarios()

    def _discover_scenarios(self):
        """扫描 scenarios 目录，加载所有有效的插件文件夹"""
        if not self.base_path.exists():
            os.makedirs(self.base_path, exist_ok=True)
            return

        for scenario_dir in self.base_path.iterdir():
            if scenario_dir.is_dir() and (scenario_dir / "config.json").exists():
                name = scenario_dir.name
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
                print(f"📦 [场景管理器] 已挂载插件: {name}")

    def get_style_mappings(self, scenario_id: str) -> Dict[str, Dict[str, str]]:
        """获取场景专属的样式翻译词典"""
        return self.scenarios.get(scenario_id, self.scenarios.get("general", {})).get("config", {}).get("style_mappings", {})

    def get_tools_whitelist(self, scenario_id: str) -> List[str]:
        """获取场景工具白名单"""
        return self.scenarios.get(scenario_id, self.scenarios.get("general", {})).get("config", {}).get("tools_whitelist", [])

    def get_contract(self, scenario_id: str) -> Dict[str, Any]:
        """获取业务原型契约"""
        return self.scenarios.get(scenario_id, self.scenarios.get("general", {})).get("config", {}).get("contract", {})

# 全局单例
scenario_manager = ScenarioManager()
