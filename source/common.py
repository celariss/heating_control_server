__author__      = "Jérôme Cuq"

import logging

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