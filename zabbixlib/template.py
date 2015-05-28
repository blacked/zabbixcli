import fnmatch
import logging
import os
import yaml
import pprint
from group import ZabbixGroups

logger = logging.getLogger(__name__)


class ZabbixTemplate(object):

    """
    Implements working with zabbix template objects.

    Arguments:
    zapi        (ZabbixAPI)       ZabbixAPI connector to send request.
    obj         (dict)            Dictionary discribed zabbix template.
    """

    def __init__(self, zapi, obj):
        self.zapi = zapi
        self.obj = obj
        self.obj_type = 'template'

    def _create_request(self):
        """
        Create request for template changes.

        Return  (str)   Request for changes.
        """

        return {'groups': ZabbixGroups(self.zapi, self.obj['groups']).push()}

    def push(self):
        """
        Push template object to zabbix server.
        """

        result = None
        req = self._create_request()

        # Get linked templates id
        if self.obj.get('templates'):
            req['templates'] = self.zapi.get_id(
                'template',
                self.obj['templates'])

        # Get current template id
        self.template_id = self.zapi.get_id('template', self.obj['name'])

        if self.template_id:
            req['templateid'] = self.template_id
            result = self.zapi.template.update(req)
        else:
            req['host'] = self.obj['name']
            result = self.zapi.template.create(req)

        result = result['templateids'][0]
        return result


class ZabbixTemplateFile(dict):

    """
    Load and Save locally resulting zabbix template.

    Attributes:
      name (str):           Name of template for load
      pattern (str):        Pattern to search for templates. Default: '*'
      basedir (str):        Directory that store zabbix templates.
                            Default: './templates'
      file_extension (str): Extension for template files. Default: '.yaml'
    """

    def __init__(
            self,
            name,
            pattern='*',
            basedir='./',
            file_extension='.yaml'):
        self.name = name
        self.file_extension = file_extension
        self.pattern = pattern + self.file_extension
        self.basedir = '{0}/{1}'.format(basedir, name)
        # Load template from files
        self.temlate = {}
        self.processed_items = 0
        self._files_list = self._walk()
        self._load()

    def _walk(self):
        """
        Return list of files for current template
        """

        result = []

        for root, dirs, files in os.walk(self.basedir):
            for file_ in fnmatch.filter(files, self.pattern):
                result.append(os.path.join(root, file_))

        return result

    def _merge(self, template1, template2):
        """
        Merge two templates.

        Attributes:
          template1 (dict)
          template2 (dict)
        """

        for k, v in template2.iteritems():
            if template1.get(k, {}) == {}:
                template1[k] = v
            else:
                if isinstance(template2.get(k, {}), dict):
                    template1.get(k, {}).update(v)
                elif isinstance(template2.get(k), list):
                    template1.get(k).extend(v)
                else:
                    template1[k] = v

        logger.debug('Template result:\n{0}'.format(template1))

    def _load(self):
        """
        Load current template from files and save it class variable.
        """

        result = {}

        for file_ in self._files_list:
            # Read template file
            with open(file_) as f:
                str_buf = f.read()
                # Load template
                template = yaml.safe_load(str_buf)
                logger.debug(
                    'Loaded template[{0}]:\n{1}'.format(
                        file_,
                        template))
                # Merge template
                self._merge(result, template)

        # Save template in class variable
        self.template = result
        logger.info('Template {0} was fully loaded.'.format(self.name))
        logger.debug('Combined template:\n{0}'.format(result))

        return result

    def save(self):
        """
        *** Experemental function ***
        *** Save your eyes - don't read the code ***

        Save dump of config to disk.
        """

        result = {}
        for k, v in self.template.iteritems():
            if isinstance(v, dict):
                result[k] = []
                if k == 'application':
                    for app, items in self.template['application'].iteritems():
                        file_ = '{0}/items/{1}{2}'.format(
                            self.basedir,
                            app.lower(),
                            self.file_extension)
                        result['application'].append(file_)
                        str_buf = yaml.safe_dump(items)
                        with open(file_ + '_', 'w') as f:
                            f.write(str_buf)
                elif k == 'triggers':
                    file_ = '{0}/triggers{1}'.format(
                        self.basedir,
                        self.file_extension)
                    result['triggers'].append(file_)

                    str_buf = yaml.safe_dump(v)
                    with open(file_ + '_', 'w') as f:
                        f.write(str_buf)
        file_ = '{0}/init{1}'.format(self.basedir, self.file_extension)
        result['init'] = file_
        init_template = dict(
            (k, v) for k, v in self.template.iteritems() if not isinstance(
                v, dict))
        str_buf = yaml.safe_dump(init_template)
        with open(result['init'] + '_', 'w') as f:
            f.write(str_buf)
        return result

    def __len__(self):
        """
        Return count of elements to process.
        """

        # TODO: Needs to refactor
        length = 1
        length += len(self.template.get('triggers', []))
        length += len(self.template.get('graphs', []))
        if self.template.get('alert', []):
            length += 1
        if self.template.get('autoreg', []):
            autoreg_len = len(self.template['autoreg'].get('add_to_group', []))
            if autoreg_len == 0 and self.template['autoreg'].get('metadata'):
                length += 1
            else:
                length += autoreg_len

        length += len(self.template.get('macros', []))
        for app, items in self.template.get('applications', {}).iteritems():
            if isinstance(items, list):
                length += len(items) + 1
            else:
                length += 1

        length += len(self.template.get('discovery', {}))
        for app, discovery in self.template.get('discovery', {}).iteritems():
            length += len(discovery.get('items', []))
            length += len(discovery.get('graphs', []))
            length += len(discovery.get('triggers', []))
            length += 1  # app

        return length

    def __getitem__(self, item, value=None):
        return self.template.get(item, value)

    def __setitem__(self, item, value):
        self.template[item] = value

    def __repr__(self):
        pf = pprint.PrettyPrinter(indent=4).pformat
        return pf(self.template)

    def iteritems(self):
        return iter(self.template.iteritems())

    def get(self, item, value=None):
        return self.__getitem__(item, value)

    def __bool__(self):
        return bool(self.template)

    __nonzero__ = __bool__