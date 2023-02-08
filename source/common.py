__author__      = "Jérôme Cuq"

import logging

### each key in list can be either :
### - a tuple (key:str, noneAllowed:bool) : the key must exists, noneAllowed indicates if None is allowed has given key value
### - a mandatory key name : the key must exists and have a actual value (not None)
def get_missing_mandatories(dico:dict, keys_list:list) -> list:
    result = []
    for item in keys_list:
        if isinstance(item,tuple):
            key = item[0]
            noneAllowed = item[1]
        else:
            key = item
            noneAllowed = False
        if (not key in dico) or (noneAllowed==False and dico[key]==None):
            result.append(key)
    return result

def toFloat(element: any, logger:logging.Logger, error_prefix:str='', default:any=None) -> float:
    if not element is None:
        if isinstance(element,float):
            return element
        try:
            return float(element)
        except ValueError:
            pass
    logger.error(error_prefix+"a float was expected, got '"+str(element)+"'")
    return default

def toInt(element: any, logger:logging.Logger, error_prefix:str='', default:any=None) -> int:
    if not element is None:
        if isinstance(element,int):
            return element
        try:
            return int(element)
        except ValueError:
            pass
    logger.error(error_prefix+"an integer was expected, got '"+str(element)+"'")
    return default