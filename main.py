import logging
import os
import sys
from json import JSONDecodeError
from typing import Callable, Optional

from config_file import ConfigFile
from renamer import Renamer
from scaner import Scaner
from scraper import CachedScraper, Locale


class Main:
    def __init__(self):
        # 配置文件
        config_file_path = os.path.join('config.json')
        self.__config_file = ConfigFile(config_file_path)

    def run_renamer(self, root_path_list: list[str]):
        try:
            config = self.__config_file.load_config()  # 从配置文件中读取配置
        except JSONDecodeError as err:
            logging.error(f'配置文件解析失败："{os.path.normpath(self.__config_file.file_path)}"')
            logging.error(f'JSONDecodeError: {str(err)}')
            return
        except FileNotFoundError as err:
            logging.error(f'配置文件加载失败："{os.path.normpath(self.__config_file.file_path)}"')
            logging.error(f'FileNotFoundError: {err.strerror}')
            return

        # 检查配置是否合法
        strerror_list = ConfigFile.verify_config(config)
        if len(strerror_list) > 0:
            logging.error(f'配置文件验证失败："{os.path.normpath(self.__config_file.file_path)}"')
            for strerror in strerror_list:
                logging.error(strerror)
            return

        # 配置 scaner
        scaner_max_depth = config['scaner_max_depth']
        scaner = Scaner(max_depth=scaner_max_depth)

        # 配置 scraper
        scraper_locale = config['scraper_locale']
        scraper_http_proxy = config['scraper_http_proxy']
        if scraper_http_proxy:
            proxies = {
                'http': scraper_http_proxy,
                'https': scraper_http_proxy
            }
        else:
            proxies = None
        scraper_connect_timeout = config['scraper_connect_timeout']
        scraper_read_timeout = config['scraper_read_timeout']
        scraper_sleep_interval = config['scraper_sleep_interval']
        cached_scraper = CachedScraper(
            locale=Locale[scraper_locale],
            connect_timeout=scraper_connect_timeout,
            read_timeout=scraper_read_timeout,
            sleep_interval=scraper_sleep_interval,
            proxies=proxies)
        tags_option = {
            'ordered_list': config['renamer_tags_ordered_list'],
            'max_number': 999999 if config['renamer_tags_max_number'] == 0 else config['renamer_tags_max_number'],
        }

        # 配置 renamer
        renamer = Renamer(
            scaner=scaner,
            scraper=cached_scraper,
            template=config['renamer_template'],
            delimiter=config['renamer_delimiter'],
            exclude_square_brackets_in_work_name_flag=config['renamer_exclude_square_brackets_in_work_name_flag'],
            renamer_illegal_character_to_full_width_flag=config['renamer_illegal_character_to_full_width_flag'],
            tags_option=tags_option)

        # 执行重命名
        for root_path in root_path_list:
            renamer.rename(root_path)


if __name__ == '__main__':
    main = Main()
    main.run_renamer(sys.argv[1:])
