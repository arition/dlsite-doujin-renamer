from typing import Optional


def ask_yes_no(prompt: str) -> bool:
    '''
    提示用户输入是否继续
    '''
    while True:
        ans = input(prompt)
        if ans in ['y', 'Y', 'yes', 'Yes', 'YES']:
            return True
        elif ans in ['n', 'N', 'no', 'No', 'NO']:
            return False


def ask_input(prompt: str, default: Optional[str] = None) -> str:
    '''
    提示用户输入
    '''
    while True:
        ans = input(prompt).strip()
        if ans != '':
            return ans
        elif default is not None:
            return default
