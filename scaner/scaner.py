import os


class Scaner(object):
    def __init__(self, max_depth=5):
        self.__max_depth = max_depth

    def scan(self, root_path: str, _depth=0):
        """
        生成器。
        """
        if os.path.isdir(root_path):  # 检查是否是文件夹
            yield root_path
            if _depth < self.__max_depth:
                dir_list = sorted(os.listdir(root_path))
                for folder in dir_list:
                    folder_path = os.path.join(root_path, folder)
                    yield from self.scan(folder_path, _depth + 1)
