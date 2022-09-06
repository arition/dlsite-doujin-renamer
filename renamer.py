from scraper import Dlsite
from typing import List
import logging
import os
import re
import shutil

import requests
import mutagen
from requests.exceptions import RequestException, ConnectionError, HTTPError, Timeout

from scaner import Scaner
from scraper import WorkMetadata, Scraper
from console_utils import ask_yes_no, ask_input

# Windows 系统的保留字符
# https://docs.microsoft.com/zh-cn/windows/win32/fileio/naming-a-file
# <（小于）
# >（大于）
# ： (冒号)
# "（双引号）
# /（正斜杠）
# \ (反反)
# | (竖线或竖线)
# ? （问号）
# * (星号)
WINDOWS_RESERVED_CHARACTER_PATTERN = re.compile(r'[\\/*?:"<>|]')
WINDOWS_RESERVED_CHARACTER_PATTERN_str = r'\/:*?"<>|'  # 半角字符，原
WINDOWS_RESERVED_CHARACTER_PATTERN_replace_str = '＼／：＊？＂＜＞｜'  # 全角字符，替


def _get_logger():
    # create logger
    logger = logging.getLogger('Renamer')
    logger.setLevel(logging.INFO)

    # create console handler and set level to info
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # add formatter to ch
    ch.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(ch)

    return logger


class Renamer(object):
    logger = _get_logger()

    def __init__(
            self,
            scaner: Scaner,
            scraper: Scraper,
            template: str = '[maker_name][rjcode] work_name cv_list_str',  # 模板
            delimiter: str = ' ',  # 列表转字符串的分隔符
            exclude_square_brackets_in_work_name_flag: bool = False,  # 设为 True 时，移除 work_name 中【】及其间的内容
            renamer_illegal_character_to_full_width_flag: bool = False,  # 设为 True 时，新文件名将非法字符转为全角；为 False 时直接移除.
            tags_option: dict = None,  # 标签相关设置
    ):
        if 'rjcode' not in template:
            raise ValueError  # 重命名不能丢失 rjcode
        self.__scaner = scaner
        self.__scraper = scraper
        self.__template = template
        self.__delimiter = delimiter
        self.__exclude_square_brackets_in_work_name_flag = exclude_square_brackets_in_work_name_flag
        self.__renamer_illegal_character_to_full_width_flag = renamer_illegal_character_to_full_width_flag
        self.__tags_option = tags_option

    def __cleanup_work_name(self, work_name: str) -> str:
        work_name = re.sub(r'【.*?】', '', work_name).strip() \
            if self.__exclude_square_brackets_in_work_name_flag \
            else work_name
        return work_name

    def __replace_tags(self, tags: List[str]) -> List[str]:
        tags_list = []
        tags_list_flag = []
        for i in self.__tags_option['ordered_list']:  # ordered_list中存在的标签
            if isinstance(i, str) and i in tags:
                tags_list.append(i)
                tags_list_flag.append(i)
            elif isinstance(i, list) and i[0] in tags:
                tags_list.append(i[1])  # 替换新标签
                tags_list_flag.append(i[0])
        for i in tags:  # 剩余的标签
            if not i in tags_list_flag:
                tags_list.append(i)
        tags_list = tags_list[: self.__tags_option['max_number']]  # 数量限制
        return tags_list

    def __compile_new_name(self, name) -> str:
        '''
        根据作品的元数据编写出新的文件名
        '''
        new_name = name

        # 文件名中不能包含 Windows 系统的保留字符
        if self.__renamer_illegal_character_to_full_width_flag:  # 半角转全角
            new_name = new_name.translate(new_name.maketrans(
                WINDOWS_RESERVED_CHARACTER_PATTERN_str, WINDOWS_RESERVED_CHARACTER_PATTERN_replace_str))
        else:  # 直接移除
            new_name = WINDOWS_RESERVED_CHARACTER_PATTERN.sub('', new_name)

        return new_name.strip()

    def __sniff_name(self, name: str) -> str:
        '''
        Get title from filename
        '''
        result = re.search(r'^\d*[_\.、\s]*(.+)\.\w+$', name)
        if result:
            return result.group(1)

    def __sniff_name_from_folder(self, name: str) -> str:
        '''
        Get title from filename
        '''
        result = re.search(r'^\d*[_\.、\s]*(.+)$', name)
        if result:
            return result.group(1)

    def __rename(self, folder_path: str, new_basename: str) -> None:
        dirname, basename = os.path.split(folder_path)
        new_folder_path = os.path.join(dirname, new_basename)
        try:
            os.rename(folder_path, new_folder_path)
        except FileExistsError as err:
            filename = os.path.normpath(err.filename)
            filename2 = os.path.normpath(err.filename2)
            raise FileExistsError(f'{filename} -> {filename2}') from err

    def __mkdir(self, metadata: WorkMetadata, target_path: str):
        path = os.path.join(target_path, self.__compile_new_name(metadata['maker_name']))
        if not os.path.exists(path):
            os.mkdir(path)
        path = os.path.join(path, self.__compile_new_name(self.__cleanup_work_name(metadata['work_name'])))
        if not os.path.exists(path):
            os.mkdir(path)
        return path

    def __download_cover(self, metadata: WorkMetadata, target_path: str) -> str:
        cover_url = metadata['cover_url']
        path = os.path.join(target_path, 'cover.jpg')
        try:
            with open(path, 'wb') as f:
                with requests.get(cover_url, stream=True) as r:
                    r.raise_for_status()
                    shutil.copyfileobj(r.raw, f)
            return path
        except Exception as err:
            raise RuntimeError(f'Cannot download cover: {cover_url} -> {path}') from err

    def __write_tag(self, title: str, metadata: WorkMetadata, target_path: str, **kwargs: str):
        file = mutagen.File(target_path, easy=True)
        file['title'] = title
        file['artist'] = metadata['cvs']
        file['albumartist'] = metadata['maker_name']
        file['album'] = self.__cleanup_work_name(metadata['work_name'])
        file['date'] = metadata['release_date']
        rjcode = metadata['rjcode']
        file['website'] = f'https://www.dlsite.com/maniax/work/=/product_id/{rjcode}.html'
        file['genre'] = self.__replace_tags(metadata['tags'])
        for key in kwargs:
            if kwargs[key] is not None:
                file[key] = kwargs[key]
        file.save()

    def __write_tag_cover(self, cover: str, target_path: str):
        if os.path.exists(cover):
            with open(cover, 'rb') as f:
                cover_data = f.read()

            file = mutagen.File(target_path)
            if type(file).__name__ == 'MP3':
                file['APIC'] = mutagen.id3.APIC(
                    encoding=mutagen.id3.Encoding.UTF8,
                    mime='image/jpeg',
                    type=mutagen.id3.PictureType.COVER_FRONT,
                    desc=u'Cover',
                    data=cover_data
                )
                file.save()
            elif type(file).__name__ == 'FLAC':
                image = mutagen.flac.Picture()
                image.type = mutagen.id3.PictureType.COVER_FRONT
                image.mime = 'image/jpeg'
                image.desc = u'Cover'
                image.data = cover_data
                file.add_picture(image)
                file.save()

    def __process_folder(self, source_path: str, target_path: str, metadata: WorkMetadata, disc_number: int) -> int:
        files = os.listdir(source_path)

        for extension in ['flac', 'mp3']:
            # ask if the audio file should be added
            audio_files = sorted([f for f in [os.path.join(source_path, f) for f in files]
                                  if os.path.isfile(f) and f.endswith(f'.{extension}')])
            if len(audio_files) == 0:
                continue
            print(f'Find {len(audio_files)} {extension} files in {source_path}')
            reply = ask_yes_no('Add these files? (y/n) ')
            if not reply:
                continue

            # ask for disc number and disc subtitle
            user_disc_number = ask_input(f'Disc number (default {disc_number}): ', str(disc_number))
            try:
                disc_number = int(user_disc_number)
            except ValueError:
                disc_number = disc_number
            disc_subtitle = os.path.basename(source_path)
            Renamer.logger.debug(f'source_path os.path.basename: {disc_subtitle}')
            disc_subtitle = self.__sniff_name_from_folder(os.path.basename(source_path))
            reply = ask_yes_no(f'Use disc subtitle: [{disc_subtitle}]? (y/n) ')
            if not reply:
                disc_subtitle = ask_input('Disc subtitle: ', '')
                if disc_subtitle == '':
                    disc_subtitle = None
                    print(f'No disc subtitle')
            Renamer.logger.debug(f'disc_number: {disc_number}, disc_subtitle: {disc_subtitle}')

            # copy and write tag
            for index, audio_file in enumerate(audio_files):
                title = self.__sniff_name(os.path.basename(audio_file))
                cover_path = os.path.join(target_path, 'cover.jpg')
                target_file = os.path.join(target_path, os.path.basename(audio_file))

                shutil.copyfile(audio_file, os.path.join(target_path, target_file))
                self.__write_tag(title, metadata, target_file, tracknumber=f'{index + 1}',
                                 discnumber=str(disc_number), discsubtitle=disc_subtitle)
                self.__write_tag_cover(cover_path, target_file)

            disc_number += 1
        return disc_number

    def rename(self, root_path: str, dest_path: str) -> None:
        work_folders = self.__scaner.scan(root_path)

        for folder_path in work_folders:
            rjcode = Dlsite.parse_rjcode(os.path.basename(folder_path))
            if not rjcode:  # 检查文件夹名称中是否含RJ号
                continue

            Renamer.logger.info(f'[{rjcode}] -> 发现 RJ 文件夹："{os.path.normpath(folder_path)}"')
            try:
                metadata = self.__scraper.scrape_metadata(rjcode)
            except Timeout:
                # 请求超时
                Renamer.logger.warning(f'[{rjcode}] -> 重命名失败：dlsite.com 请求超时！\n')
                continue
            except ConnectionError as err:
                # 遇到其它网络问题（如：DNS 查询失败、拒绝连接等）
                Renamer.logger.warning(f'[{rjcode}] -> 重命名失败：{str(err)}\n')
                continue
            except HTTPError as err:
                # HTTP 请求返回了不成功的状态码
                Renamer.logger.warning(f'[{rjcode}] -> 重命名失败：{err.response.status_code} {err.response.reason}\n')
                continue
            except RequestException as err:
                # requests 引发的其它异常
                Renamer.logger.error(f'[{rjcode}] -> 重命名失败：{str(err)}\n')
                continue

            try:
                Renamer.logger.info(f'[{rjcode}] -> Processing')
                Renamer.logger.info(f'[{rjcode}] -> Create folder structure')
                target_path = self.__mkdir(metadata, dest_path)
                Renamer.logger.info(f'[{rjcode}] -> Download cover')
                self.__download_cover(metadata, target_path)
                Renamer.logger.info(f'[{rjcode}] -> Start interactive renaming')
                disc_number = 1
                for source_path in self.__scaner.scan(folder_path):
                    disc_number = self.__process_folder(source_path, target_path, metadata, disc_number)
            except Exception as err:
                Renamer.logger.error(f'[{rjcode}] -> 重命名失败：{str(err)}\n')
                raise err
                continue
            Renamer.logger.info(f'[{rjcode}] -> 重命名成功')
