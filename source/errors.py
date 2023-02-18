__author__      = "Jérôme Cuq"

from enum import Enum
import logging

class ECfgError(Enum):
    # An exception has occured
    # params : {'exception':str}
    EXCEPTION = 1

    # The configuration file is missing
    # params : {'filename':str}
    MISSING_FILE = 2

    # The configuration file content format is invalid
    # params : {'error':str}
    BAD_FILE_CONTENT = 3

    # One or more mandatory children nodes are missing
    # params : {'missing_children':list[str]}
    MISSING_NODES  = 4
    
    # The node's value is a reference to a missing node
    # params : {'reference':str}
    BAD_REFERENCE  = 5

    # Bad type, a list was expected for this node's value
    # params : {}
    EXPECTED_LIST  = 6
    
    # A unique key identifier has been used twice 
    # params : {'key':str}
    DUPLICATE_UNIQUE_KEY  = 7
    
    # Expected one or more children for list node
    # params : {'child_node':str}
    EMPTY_LIST = 8
    
    # The node's value is not allowed
    # params : {'value':str}
    BAD_VALUE = 9
    
    # Circular references
    # params : {'aliases':list}
    CIRCULAR_REF = 10
    
    # Missing value in list
    # params : {'value':str}
    MISSING_VALUE = 11
    
    

class CfgError(Exception):
    def __init__(self, id:ECfgError, node_path:str, node_key:str=None, params:dict={}, logger:logging.Logger = None):
        if not id in ECfgError:
            raise ValueError("Error with id <"+str(id)+"> is not declared")
        self.id:ECfgError = id
        self.params:dict = params
        self.node:str = node_path.split('/')[-1]
        self.node_key:str = node_key
        self.node_path:str = node_path
        self.generic_desc:str = ''
        nodes_desc = self.node_path+("['"+self.node_key+"']" if self.node_key else "")
        if self.id==ECfgError.EXCEPTION: self.generic_desc = "An Exception has occured : "+str(self.params['exception'])
        elif self.id==ECfgError.MISSING_FILE: self.generic_desc = "Configuration file is missing : "+str(self.params['filename'])
        elif self.id==ECfgError.BAD_FILE_CONTENT: self.generic_desc = "Configuration file content is invalid : "+str(self.params['error'])
        elif self.id==ECfgError.MISSING_NODES: self.generic_desc = "Missing mandatory node(s) in <"+nodes_desc+"> : "+str(self.params['missing_children'])
        elif self.id==ECfgError.BAD_REFERENCE: self.generic_desc = "Reference to a node in <"+nodes_desc+"> that does not exist : "+str(self.params['reference'])
        elif self.id==ECfgError.EXPECTED_LIST: self.generic_desc = "A list was expected for node <"+nodes_desc+">"
        elif self.id==ECfgError.DUPLICATE_UNIQUE_KEY: self.generic_desc = "The unique key '"+str(self.params['key'])+"' in node '"+nodes_desc+"' was already declared"
        elif self.id==ECfgError.EMPTY_LIST: self.generic_desc = "The child node '"+str(self.params['child_node'])+"' in '"+nodes_desc+"' must contain an non empty list"
        elif self.id==ECfgError.BAD_VALUE: self.generic_desc = "Invalid value for node <"+nodes_desc+"> : "+str(self.params['value'])
        elif self.id==ECfgError.MISSING_VALUE: self.generic_desc = "A value was expected in list for node <"+nodes_desc+"> : "+str(self.params['value'])
        elif self.id==ECfgError.CIRCULAR_REF: self.generic_desc = "Circular dependency detected between items "+str(self.params['aliases'])+" in <"+nodes_desc+">"
        else: self.generic_desc = "Unknown error"
        if logger:
            logger.error(self.generic_desc)
    
    # @return dict content : self.params + {'node':str, ['node_key':str], 'node_path':str, 'generic_desc':str}
    def to_string(self) -> str:
        return self.generic_desc
        
    def to_dict(self) -> dict:
        params = self.params.copy()
        params['id'] = self.id.name
        params['node'] = self.node
        params['node_path'] = self.node_path
        params['generic_desc']= self.to_string()
        if self.node_key:
            params['node_key'] = self.node_key
        return params
