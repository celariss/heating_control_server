import yaml, re, os

class YamlTagsResolver :
    """
    This class extends yaml loader to process the following tags in yaml data :
    - !secret
    - !env

    see : https://matthewpburruss.com/post/yaml/
    """
    

    envvar_pattern = re.compile('.*?\${(\w+)}.*?')
    """pattern for global vars: look for ${word}"""
    
    secretsdata = None        

    def create_yaml_loader(secret_filename:str) -> yaml.BaseLoader:
        """Create a yaml loader able to process tags in yaml data

        :param secret_filename: yaml file that contains secrets, may not exist
        :type secret_filename: str
        :return: the created loader
        :rtype: yaml.BaseLoader
        """
        loader = yaml.SafeLoader
        YamlTagsResolver.add_yaml_resolver_for_secrets(loader, secret_filename)
        YamlTagsResolver.add_yaml_resolver_for_envvar(loader)
        return loader

    def add_yaml_resolver_for_secrets(loader:yaml.BaseLoader, secret_filename:str, tag='!secret'):
        if os.path.exists(secret_filename):
            with open(secret_filename, 'r', encoding='utf-8') as secrets_file:
                YamlTagsResolver.secretsdata = yaml.load(secrets_file,Loader=yaml.Loader)
        def ctor_for_secrets(loader:yaml.BaseLoader, node:yaml.nodes.ScalarNode):
            value = loader.construct_scalar(node)
            if YamlTagsResolver.secretsdata and isinstance(YamlTagsResolver.secretsdata, dict):
                if value in YamlTagsResolver.secretsdata:
                    return YamlTagsResolver.secretsdata[value]
            return value
        loader.add_constructor(tag, ctor_for_secrets)

    def add_yaml_resolver_for_envvar(loader:yaml.BaseLoader, tag='!env'):
        """
        source : https://medium.com/swlh/python-yaml-configuration-with-environment-variables-parsing-77930f4273ac
        Add a resolver in given loader to resolve any environment variables
        The environment variables must have !env before them and be in this format
        to be parsed: ${VAR_NAME}.
        E.g.:
        database:
            host: !env ${HOST}
            port: !env ${PORT}
        app:
            log_path: !env '/var/${LOG_PATH}'
            something_else: !env '${AWESOME_ENV_VAR}/var/${A_SECOND_AWESOME_VAR}'
        :param yaml.BaseLoader loader: the loader to add the resolver to
        :param str tag: the tag to look for
        """

        def ctor_for_envvar(loader:yaml.BaseLoader, node:yaml.nodes.ScalarNode):
            """
            Extracts the environment variable from the node's value

            :param yaml.Loader loader: the yaml loader
            :param node: the current node in the yaml
            :return: the parsed string that contains the value of the environment
            variable
            """
            value = loader.construct_scalar(node)
            match = YamlTagsResolver.envvar_pattern.findall(value)  # to find all env variables in line
            if match:
                full_value = value
                for g in match:
                    full_value = full_value.replace(
                        f'${{{g}}}', os.environ.get(g, g)
                    )
                return full_value
            return value

        loader.add_constructor(tag, ctor_for_envvar)