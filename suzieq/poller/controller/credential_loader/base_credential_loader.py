"""This module contains the base class for plugins which loads
devices credentials
"""
import logging
from abc import abstractmethod
from typing import Dict, List, Type

from suzieq.poller.controller.base_controller_plugin import ControllerPlugin
from suzieq.shared.exceptions import InventorySourceError

logger = logging.getLogger(__name__)


class CredentialLoader(ControllerPlugin):
    """Base class used to import device credentials from different
    sources
    """

    def __init__(self, init_data: Dict) -> None:
        super().__init__()

        self._cred_format = [
            'username',
            'password',
            'ssh_keyfile',
            'passphrase'
        ]

        # load auth parameters

        self._name = init_data.get('name')

        self._valid_fields = ['name', 'type']

        self._validate_config(init_data)

        self.init(init_data)

    @abstractmethod
    def init(self, init_data: Type):
        """Initialize the object

        Args:
            init_data (Type): data used to initialize the object
        """

    @abstractmethod
    def load(self, inventory: Dict[str, Dict]):
        """Loads the credentials inside the inventory

        Args:
            inventory (Dict[str, Dict]): inventory to update
        """

    def _validate_config(self, config: Dict):
        """Validate configuration

        Reads the valid fields from

        Args:
            config (Dict): configuration dictionary
        """
        inv_fields = [x for x in config if x not in self._valid_fields]
        if inv_fields:
            raise InventorySourceError(
                f'{self._name}: unknown fields {inv_fields}')

    def write_credentials(self, device: Dict, credentials: Dict[str, Dict]):
        """write and validate input credentials for a device

        Args:
            device (Dict): device to add credentials
            credentials (Dict[str, Dict]): device's credentials

        Raises:
            InventorySourceError: Invalid credentials
        """
        missing_keys = self._validate_credentials(credentials)
        if missing_keys:
            raise InventorySourceError(
                f'Invalid credentials: missing keys {missing_keys}')
        device.update(credentials)

    def _validate_credentials(self, credentials: Dict) -> List[str]:
        """Checks if provided credentials are valid

        Args:
            credentials (Dict): device credentials

        Raises:
            RuntimeError: Unexpected key

        Returns:
            List[str]: list of missing fields
        """
        cred_keys = set(self._cred_format)
        for key, value in credentials.items():
            if key in cred_keys:
                # 'passphrase' is valid also with None value
                # Also 'password' and 'ssh_keyfile' with None value are valid
                # but only if at least one of them has a not None value
                if value or key == 'passphrase':
                    cred_keys.remove(key)
            else:
                raise InventorySourceError(
                    f'Unexpected key {key} in credentials')

        # One between password or ssh_keyfile must be defines
        if 'password' in cred_keys and 'ssh_keyfile' in cred_keys:
            cred_keys.remove('password')
            cred_keys.remove('ssh_keyfile')
            ret = list(cred_keys)
            ret.append('password or ssh_keyfile')
            return ret

        # if we arrived at this point, password or ssh_keyfile
        # is set. Remove the not set one
        if 'password' in cred_keys:
            cred_keys.remove('password')

        if 'ssh_keyfile' in cred_keys:
            cred_keys.remove('ssh_keyfile')

        return list(cred_keys)
