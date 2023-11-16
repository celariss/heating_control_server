import sys
import os
import shutil
import importlib.util
import configparser
import re

try:
    from ruamel.yaml import *
    from ruamel.yaml.scanner import ScannerError
except ImportError:
    ruamel_available = False
else:
    ruamel_available = True

# Pattern to get version from string :
#   A.B.C.DbE
# with optional D, some optional characters before A, and optional build version E
version_re: re.Pattern = re.compile('[a-zA-Z]*(\\d+)\\.(\\d+)\\.(\\d+)(?:\\.(\\d+))?(?:b(\\d+))?')


def exit_script(value: int = 1):
    log('exiting...')
    exit(1)


def log(message: str):
    print(message)


def log_error(message: str, exitScript: bool = True):
    """print an error and stop current script

    :param message: message to print out
    :type message: str
    :param exitScript: indicates whether the function must call exit, defaults to True
    :type exitScript: bool, optional
    """
    print("ERROR: "+message, file=sys.stderr)
    if exitScript:
        exit_script()


def read_ini_file(filepath: str, section_name: str, mandatory_params: list) -> dict[str]:
    """Read given parameters from a INI file

    :param filepath: path to INI file to read from
    :type filepath: str
    :param section_name: section name to get params from
    :type section_name: str
    :param mandatory_params: list of parameters to read. 
                             Each value is either a str (param name) or a tuple (param_name, value_type)
                             Where value_type must be in [str, int, float, bool]
    :type mandatory_params: list
    :return: dictionnary containing all requested parameters value
    :rtype: dict[str]
    """
    if not os.path.exists(filepath):
        log_error("Missing file : "+filepath)
    config = configparser.ConfigParser()
    config.read(filepath)
    if not section_name in config:
        log_error("Section ["+section_name +
                  "] is missing in file '"+filepath+"'")
    section = config[section_name]
    params = {}
    for item in mandatory_params:
        if isinstance(item, tuple):
            (name, type_) = item
        else:
            name = item
            type_ = str
        if not name in section:
            log_error("'"+filepath+"' : Parameter '"+name +
                      "' is missing in section ["+section_name+"]")
        if type_ == int:
            params[name] = to_int(section[name], "Parameter '"+name+"'")
        elif type_ == float:
            params[name] = to_float(section[name], "Parameter '"+name+"'")
        elif type_ == bool:
            params[name] = to_bool(section[name], "Parameter '"+name+"'")
        elif type_ == str:
            params[name] = section[name]
        else:
            log_error("Parameter '"+name +
                      "' : unsupported type '"+str(type_)+"'")
    return params

def compare_versions(version1:str, version2:str) -> int:
    match1:re.Match = version_re.match(version1)
    match2:re.Match = version_re.match(version2)
    bad_version = None
    if not match1 or len(match1.groups())<3: bad_version = version1
    if not match2 or len(match2.groups())<3: bad_version = version2
    if bad_version:
        log_error("Bad version string: "+bad_version)
    for i in range(5):
        v1 = int(match1.group(i+1)) if match1.group(i+1) else 0
        v2 = int(match2.group(i+1)) if match2.group(i+1) else 0
        if v1 != v2:
            return v1 - v2
    return 0

def copy_file(src: str, dst: str, srcMustExist: bool = True):
    #log("Copying file '"+src+"' to '"+dst+"' ...")
    if os.path.exists(src):
        shutil.copy(src, dst)
    elif srcMustExist:
        log_error("Missing file : "+src)


def copy_folder(src: str, dst: str, srcMustExist: bool = True, mergeDst: bool = False, ignore=None):
    """Copy folder, even if target folder already exists

    The optional ignore argument is a callable. If given, it
    is called with the `src` parameter, which is the directory
    being visited by copytree(), and `names` which is the list of
    `src` contents, as returned by os.listdir():

        callable(src, names) -> ignored_names

    :param src: source folder path
    :type src: str
    :param dst: target folder path
    :type dst: str
    :param srcMustExist: If True, check the src path (and log an error), defaults to True
    :type srcMustExist: bool, optional
    :param mergeDst: If True the target is not removed, defaults to False
    :type mergeDst: bool, optional
    :param ignore: If not None, callable to call to get files to ignore
    :type ignore: callable(src, names) -> ignored_names, optional
    """
    log("Copying folder '"+src+"' to '"+dst+"' ...")
    if os.path.exists(src):
        if (not mergeDst) and os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst, dirs_exist_ok=mergeDst, ignore=ignore)
    elif srcMustExist:
        log_error("Missing folder : "+src)


def remove_file(path: str, save_suffix: str = '~'):
    """Make a copy of a file, using given suffix, before removing it.
    Does not complain if file to remove does not exist

    :param path: path to file to remove
    :type path: str
    :param save_suffix: If not None, the file is saved with given suffix, defaults to '~'
    :type save_suffix: str, optional
    """
    if os.path.exists(path):
        if save_suffix:
            log("...saving file '"+path+"' to '"+path+save_suffix+"'")
            move_file(path, path+save_suffix, None)
        else:
            os.remove(path)


def move_file(src: str, dst: str, save_suffix: str = '~'):
    """Move file even if target already exist

    :param src: _description_
    :type src: str
    :param dst: _description_
    :type dst: str
    :param save_suffix: If not None, the file is saved with given suffix, defaults to '~'
    :type save_suffix: str, optional
    """
    if os.path.exists(src):
        if os.path.exists(dst):
            remove_file(dst, save_suffix)
        os.rename(src, dst)


def check_path_is_writable(path: str):
    """Check if given path is writable by current user/script.
    If path is not writable, an error is printed and the script is stopped.

    This function looks for the last level, in the given path, 
    that actually exists on disk to check the write access.

    :param path: _description_
    :type path: str
    :return: _description_
    :rtype: _type_
    """
    path_ = path
    while not os.path.exists(path_):
        try:
            path_ = os.path.dirname(path_)
        except Exception:
            return False
    if not os.access(path_, os.W_OK):
        log_error("Following path is not writable : "+path)


def get_python_global(filepath: str, name: str) -> object:
    if os.path.exists(filepath):
        spec = importlib.util.spec_from_file_location("", filepath)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except:
            pass
        try:
            return getattr(mod, name)
        except AttributeError:
            pass
    return None


def ask_user(question: str, allowedAnswers: list[str], default: str = None) -> str:
    text: str = ' ('
    for i in range(len(allowedAnswers)):
        answer: str = allowedAnswers[i]
        if i > 0:
            text = text + '|' + answer
        else:
            text = text + answer
    text: str = text + ') : [' + default + '] '

    # We ask user ignoring answer casing
    answers: list[str] = [answer.lower() for answer in allowedAnswers]
    cur_answer: str = None
    while not cur_answer in answers:
        if cur_answer:
            log_error('Invalid answer !', False)
        cur_answer = input(question+text).lower()
        if cur_answer == '':
            cur_answer = default
        cur_answer = cur_answer.lower()

    # Make sure to return an answer that respects allowedAnswers casing
    for answer in allowedAnswers:
        if answer.lower() == cur_answer:
            return answer
    # we shouldnt get here
    return cur_answer


def yaml_get_param(filepath: str, parampath: str, default=None, fileMustExist: bool = False) -> object:
    if not ruamel_available:
        log_error(
            "Python package 'ruamel.yaml' is missing. Install this way : `pip install ruamel.yaml`")
    yaml_data = yaml_check_file(filepath, fileMustExist)
    if yaml_data:
        (data, name) = __yaml_find_param(yaml_data, parampath)
        if data:
            return data[name]
    return default


def yaml_set_params(filepath: str, params: list[(str, str)], fileMustExist: bool = True) -> bool:
    if not ruamel_available:
        log_error(
            "Python package 'ruamel.yaml' is missing. Install this way : `pip install ruamel.yaml`")
    yaml_data = yaml_check_file(filepath, fileMustExist)
    if yaml_data:
        save: bool = False
        for param in params:
            (parampath, value) = param
            (data, name) = __yaml_find_param(yaml_data, parampath)
            if data:
                log("  -> Setting '"+parampath+"' = "+str(value))
                data[name] = value
                save = True
        if save:
            with open(filepath, 'w', encoding='utf-8') as data_file:
                yaml = YAML(typ='rt')
                yaml.dump(yaml_data, data_file)
            return True
    return False


def yaml_check_file(filepath: str, mustExist: bool = True) -> object:
    if not ruamel_available:
        log_error(
            "Python package 'ruamel.yaml' is missing. Install this way : `pip install ruamel.yaml`")
    if not os.path.exists(filepath):
        if mustExist:
            log_error("Missing file : "+filepath)
    else:
        yaml = YAML(typ='rt')
        try:
            with open(filepath, 'r', encoding='utf-8') as data_file:
                return yaml.load(data_file)
        except ScannerError as exc:
            log_error(exc.problem_mark.name+', line ' +
                      str(exc.problem_mark.line)+' : '+exc.problem)


def yaml_patch_file(patch_filepath: str, dst_filepath: str, primary_key: str = None, save_suffix: str = '~'):
    """Put the content of source file in target file.
    Each item from source is overwritten in target if already present.

    :param patch_filepath: _description_
    :type patch_filepath: str
    :param dst_filepath: _description_
    :type dst_filepath: str
    :param primary_key: If the patch_file contains a list, the primary_key is used to find each item in dst_file
    :type primary_key: str
    :param save_suffix: If not None, the file is first saved with given suffix, defaults to '~'
    :type save_suffix: str, optional
    """

    if not ruamel_available:
        log_error(
            "Python package 'ruamel.yaml' is missing. Install this way : `pip install ruamel.yaml`")
    if not os.path.exists(patch_filepath):
        log_error("patch file does not exist : "+patch_filepath)
    if not os.path.exists(dst_filepath):
        log_error("target file does not exist : "+dst_filepath)

    if save_suffix:
        log("...saving file '"+dst_filepath+"' to '"+dst_filepath+save_suffix+"'")
        copy_file(dst_filepath, dst_filepath+save_suffix)

    yaml = YAML(typ='rt')   # default is 'rt' (round-trip), can be 'safe'
    with open(patch_filepath, 'r', encoding='utf-8') as data_file:
        patch_data = yaml.load(data_file)
    with open(dst_filepath, 'r', encoding='utf-8') as data_file:
        dst_data = yaml.load(data_file)

    if dst_data != None and type(patch_data) != type(dst_data):
        log_error("can not patch '"+dst_filepath +
                  "' : the file content is not of the same type than patch file")

    if isinstance(patch_data, dict):
        if not dst_data:
            dst_data = {}
        for key in patch_data:
            dst_data[key] = patch_data[key]

    if isinstance(patch_data, list):
        if not primary_key:
            log_error("yaml_patch_file(): 'primary_key' arg can not be null")
        if not dst_data:
            dst_data = []
        for item in patch_data:
            # searching for this item in dst_data
            if isinstance(item, dict) and len(item.keys()) > 0:
                if not primary_key in item:
                    log_error("yaml_patch_file(): missing primary_key '"+primary_key +
                              "' in patch file data (file: '"+patch_filepath+"')")
                primary_key_value = item[primary_key]
                index: int = 0
                while index < len(dst_data):
                    if primary_key in dst_data[index] and dst_data[index][primary_key] == primary_key_value:
                        # found !
                        dst_data[index] = item
                        break
                    index = index+1
                if index == len(dst_data):
                    # not found ...
                    dst_data.append(item)

    with open(dst_filepath, 'w', encoding='utf-8') as data_file:
        log('patching file : '+dst_filepath)
        yaml.dump(dst_data, data_file)


def __yaml_find_param(yaml_data, parampath: str):
    """Find the parameter in the yaml_data that fits the parampath

    :param yaml_data: yaml data structure to browse
    :type yaml_data: any
    :param parampath: path into yaml data, parts are separated by a '/' character
    :type parampath: str
    :return: tuple (parent dict, key)
    :rtype: tuple
    """

    if not ruamel_available:
        log_error(
            "Python package 'ruamel.yaml' is missing. Install this way : `pip install ruamel.yaml`")
    params = parampath.split('/')
    size = len(params)
    for i in range(size):
        param = params[i]
        if isinstance(yaml_data, list):
            if len(yaml_data) == 0:
                return (None, None)
            yaml_data = yaml_data[0]
        if not isinstance(yaml_data, dict):
            return (None, None)
        if not param in yaml_data:
            return (None, None)
        if i == size-1:
            return (yaml_data, param)
        yaml_data = yaml_data[param]


def to_float(element: any, error_prefix: str = '') -> float:
    if not element is None:
        if isinstance(element, float):
            return element
        try:
            return float(element)
        except ValueError:
            pass
    log_error(error_prefix+"a float was expected, got '"+str(element)+"'")


def to_int(element: any, error_prefix: str = '') -> int:
    if not element is None:
        if isinstance(element, int):
            return element
        try:
            return int(element)
        except ValueError:
            pass
    log_error(error_prefix+"an integer was expected, got '"+str(element)+"'")


def to_bool(element: any, error_prefix: str = '') -> bool:
    if not element is None:
        if isinstance(element, bool):
            return element
        if isinstance(element, str):
            if element.lower()=='false':
                return False
            elif element.lower()=='true':
                return True
        try:
            return bool(element)
        except ValueError:
            pass
    log_error(error_prefix+"an boolean was expected, got '"+str(element)+"'")
