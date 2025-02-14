"""This module contains the class to import device credentials using files
"""
import logging
from pathlib import Path
from typing import Dict

import yaml
from suzieq.poller.controller.credential_loader.base_credential_loader import \
    CredentialLoader
from suzieq.shared.exceptions import InventorySourceError

logger = logging.getLogger(__name__)


class CredFile(CredentialLoader):
    """Reads devices credentials from a file and write them on the inventory
    """

    def _validate_config(self, config: Dict):
        self._valid_fields.append('path')
        return super()._validate_config(config)

    def init(self, init_data: dict):

        if not init_data.get('path'):
            raise InventorySourceError(
                f'{self._name} No field <path> '
                'for device credential provided'
            )

        dev_cred_file = Path(init_data['path'])
        if not dev_cred_file.is_file():
            raise InventorySourceError(
                f'{self._name} The credential file {init_data["path"]} '
                'does not exists')
        try:
            with open(dev_cred_file, 'r') as f:
                self._raw_credentials = yaml.safe_load(f.read())
        except yaml.YAMLError:
            raise InventorySourceError(
                f'{self._name} The credential file is not a valid yaml file'
            )

        if not self._raw_credentials:
            raise InventorySourceError(
                f'{self._name} The credential file is empty'
            )

        if not isinstance(self._raw_credentials, list):
            raise InventorySourceError(
                f'{self._name} The credentials file must contain all device '
                'credential divided in namespaces'
            )

    def load(self, inventory: Dict):
        if not inventory:
            logger.info('Not loading credentials due to empty inventory')
            return

        for ns_credentials in self._raw_credentials:
            namespace = ns_credentials.get('namespace', '')
            if not namespace:
                raise InventorySourceError(
                    f'{self._name} All namespaces must have a name')

            ns_nodes = ns_credentials.get('devices', [])
            if not ns_nodes:
                logger.warning(
                    f'{self._name} No devices in {namespace} namespace')
                continue

            for node_info in ns_nodes:
                if node_info.get('hostname'):
                    node_id = node_info['hostname']
                    node_key = 'hostname'
                elif node_info.get('address'):
                    node_id = node_info['address']
                    node_key = 'address'
                else:
                    raise InventorySourceError(
                        f'{self._name} Nodes must have a hostname or '
                        'address')

                node = [x for x in inventory.values()
                        if x.get(node_key) == node_id]
                if not node:
                    logger.warning(
                        f'{self._name} Unknown node called {node_id}')
                    continue

                node = node[0]
                if namespace != node.get('namespace', ''):
                    raise InventorySourceError(
                        f'The device {node_id} does not belong the namespace '
                        f'{namespace}'
                    )
                if node_info.get('keyfile'):
                    # rename 'keyfile' into 'ssh_keyfile'
                    node_info['ssh_keyfile'] = node_info.pop('keyfile')

                if 'passphrase' not in node_info:
                    if node_info.get('key-passphrase'):
                        # rename 'key-passphrase' into 'passphrase'
                        node_info['passphrase'] = node_info.pop(
                            'key-passphrase')
                    else:
                        # set it to None
                        node_info['passphrase'] = None

                node_cred = node_info.copy()

                node_cred.pop(node_key)

                fields = ['username', 'passphrase', 'ssh_keyfile', 'password']
                multi_defined = []
                for f in fields:
                    if node.get(f) and node_cred.get(f):
                        multi_defined.append(f)
                    elif node.get(f):
                        node_cred[f] = node[f]

                if multi_defined:
                    raise InventorySourceError(
                        f"{self._name} the node {node.get('address')} has the "
                        "following strings defined in multiple places "
                        f"{multi_defined}")

                self.write_credentials(node, node_cred)

        # check if all devices has credentials
        no_cred_nodes = [
            f"{d.get('namespace')}.{d.get('address')}"
            for d in inventory.values()
            if not d.get('username', None) or
            not (d.get('password') or d.get('ssh_keyfile'))
        ]
        if no_cred_nodes:
            raise InventorySourceError(
                'No credentials to log into the following nodes: '
                f'{no_cred_nodes}'
            )
