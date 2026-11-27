# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, ValidationError, validator, Field

from module.config.utils import *


class ConfigMenu:
    # 手动的代码配置菜单
    def __init__(self) -> None:
        self.menu = {}
        # 总览
        self.menu["Overview"] = []
        self.menu['TaskList'] = []
        # 脚本设置
        self.menu['Script'] = ['Script', 'GlobalGame', 'Restart']
        # 刷御魂
        self.menu["Soul Zones"] = ['Orochi', 'Sougenbi', 'FallenSun', 'EternitySea', 'SixRealms', 'OtherWorldTwilight']
        # 日常的任务
        self.menu["Daily Task"] = ['DailyTrifles', 'AreaBoss', 'GoldYoukai', 'ExperienceYoukai', 'Nian',
                                   'TalismanPass', 'DemonEncounter', 'Pets', 'SoulsTidy', 'Delegation', 'WantedQuests',
                                   'Tako', 'AutoCheckinBigGod']
        # 其他副本
        self.menu["Other Dungeons"] = [
            "BondlingFairyland",
            "EvoZone",
            "GoryouRealm",
            "Exploration",
            "HeroTest",
            "FindJade",
            "MemoryScrolls",
            "AssistBattle",
            "AccountSwitch"
        ]
        # 寮任务
        self.menu["Guild Tasks"] = ['KekkaiUtilize', 'KekkaiActivation', 'RealmRaid', 'RyouToppa', 'Dokan', 'ZombieGuild',
                                    'CollectiveMissions',
                                    'Hunt' , 'AbyssShadows', 'GuildBanquet', 'DemonRetreat']
        # 每周任务
        self.menu["Weekly Task"] = ['TrueOrochi', 'RichMan', 'Secret', 'WeeklyTrifles', 'MysteryShop', 'Duel', 'Chess']
        # 活动的任务
        self.menu["Activity Task"] = ['ActivityShikigami', 'VersionActivity', 'LBS', 'MetaDemon', 'FrogBoss', 'FloatParade', 'DyeTrials', 'Quiz', 'GuguArtStudio', 'FrogChallenge', 'DemonDrill', 'IbukiArena']
        # 开发工具
        self.menu["Tools"] = ['Image Rule', 'Ocr Rule', 'Click Rule', 'Long Click Rule', 'Swipe Rule', 'List Rule']

    @property
    def gui_menu_list(self) -> dict:
        """返回给 OMJHelper 的菜单；无权限的任务不显示。"""
        from module.license import license_service
        from module.license.permissions import required_permission

        result: dict[str, list[str]] = {}
        for group, tasks in self.menu.items():
            if group in ('TaskList', 'Tools'):
                continue
            visible = []
            for task in tasks:
                permission = required_permission(task)
                if permission and not license_service.has_permission(permission):
                    continue
                visible.append(task)
            # 空分组不返回，避免 OMJHelper 显示空标题；Overview/Script 始终保留。
            if visible or group in ('Overview', 'Script'):
                result[group] = visible
        return result


if __name__ == "__main__":
    try:
        m = ConfigMenu()
        print(m.gui_menu_list)
    except:
        print('weih')