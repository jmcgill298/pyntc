"""Module for using an F5 TMOS device over the REST / SOAP.
"""

import hashlib
import os
import re
import time

import bigsuds
import requests
from f5.bigip import ManagementRoot

from .base_device import BaseDevice


class F5Device(BaseDevice):
    def __init__(self, host, username, password, **kwargs):
        super(F5Device, self).__init__(host, username, password, vendor='f5', device_type='f5_tmos_icontrol')
        self.vendor = 'F5 Networks'
        self.host = host
        self.username = username
        self.password = password
        self._active_volume = None
        self._facts = None
        self._free_space = None
        self._hostname = None
        self._images = None
        self._interfaces = None
        self._model = None
        self._serial_number = None
        self._uptime = None
        self._version = None
        self._vlans = None
        self._volumes = None
        self.api_handler = ManagementRoot(self.host, self.username, self.password)
        self._open_soap()

    def _check_free_space(self, min_space=0):
        """Checks for minimum space on the device.

        Returns:
            bool - True / False if min_space is available on the device.
        """
        if not self.free_space:
            raise ValueError('Could not get free space')
        elif self.free_space >= min_space:
            return True
        else:
            return False

    def _check_md5sum(self, filename, checksum):
        """Checks if md5sum is correct.

        Returns:
            bool - True / False if checksums match.
        """
        md5sum = self._file_copy_remote_md5(filename)

        if checksum == md5sum:
            return True
        else:
            return False

    @staticmethod
    def _file_copy_local_file_exists(filepath):
        return os.path.isfile(filepath)

    def _file_copy_local_md5(self, filepath, blocksize=2 ** 20):
        """Gets md5 checksum from the filepath.

        Returns:
            str - if the file exists.
            None - if the file does not exist.
        """
        if self._file_copy_local_file_exists(filepath):
            m = hashlib.md5()
            with open(filepath, "rb") as f:
                buf = f.read(blocksize)
                while buf:
                    m.update(buf)
                    buf = f.read(blocksize)
            return m.hexdigest()

    def _file_copy_remote_md5(self, filepath):
        """Gets md5 checksum of the filename.

        Example of 'md5sum' command:

        [root@ntc:Active:Standalone] config # md5sum /tmp/systemauth.pl
        c813ac405cab73591492db326ad8893a  /tmp/systemauth.pl

        Returns:
            str - md5sum of the filename.
        """
        md5sum_result = None
        md5sum_output = self.api_handler.tm.util.bash.exec_cmd('run', utilCmdArgs='-c "md5sum {}"'.format(filepath))
        if md5sum_output:
            md5sum_result = md5sum_output.commandResult
            md5sum_result = md5sum_result.split()[0]

        return md5sum_result

    def _image_match(self, image_name, checksum):
        """Checks if image name matches the checksum.

        Returns:
            bool - True / False if image matches the checksum.
        """
        if image_name in self.images:
            image = os.path.join('/shared/images', image_name)
            if self._check_md5sum(image, checksum):
                return True

        return False

    def _open_soap(self):
        try:
            self.soap_handler = bigsuds.BIGIP(hostname=self.host, username=self.username, password=self.password)
            self.devices = self.soap_handler.Management.Device.get_list()
        except bigsuds.OperationFailed as err:
            raise RuntimeError('ConfigSync API Error ({})'.format(err))

    def _reboot_to_volume(self, volume_name=None):
        """Requests the reboot (activation) to a specified volume.

        Returns:
            None
        """
        if volume_name is not None:
            self.api_handler.tm.sys.software.volumes.exec_cmd('reboot', volume=volume_name)
        else:
            # F5 SDK API does not support reboot to the current volume.
            # This is a workaround by issuing reboot command from bash directly.
            self.api_handler.tm.util.bash.exec_cmd('run', utilCmdArgs='-c "reboot"')

    def _reconnect(self):
        """ Reconnects to the device.
        """
        self.api_handler = ManagementRoot(self.host, self.username, self.password)

    def _upload_image(self, image_filepath):
        """Uploads an iso image to the device.

        Returns:
            None
        """
        image_filename = os.path.basename(image_filepath)
        _URI = 'https://{hostname}/mgmt/cm/autodeploy/software-image-uploads/{filename}'.format(
            hostname=self.host, filename=image_filename)
        chunk_size = 512 * 1024
        size = os.path.getsize(image_filepath)
        headers = {'Content-Type': 'application/octet-stream'}
        requests.packages.urllib3.disable_warnings()
        start = 0

        with open(image_filepath, 'rb') as fileobj:
            while True:
                payload = fileobj.read(chunk_size)
                if not payload:
                    break

                end = fileobj.tell()

                if end < chunk_size:
                    end = size
                content_range = "{}-{}/{}".format(start, end - 1, size)
                headers['Content-Range'] = content_range
                requests.post(_URI, auth=(self.username, self.password), data=payload, headers=headers, verify=False)

                start += len(payload)

        self.refresh_free_space()

    @staticmethod
    def _uptime_to_string(uptime):
        days = uptime / (24 * 60 * 60)
        uptime = uptime % (24 * 60 * 60)
        hours = uptime / (60 * 60)
        uptime = uptime % (60 * 60)
        mins = uptime / 60
        uptime = uptime % 60
        seconds = uptime

        return '%02d:%02d:%02d:%02d' % (days, hours, mins, seconds)

    def _volume_exists(self, volume_name):
        """Checks if volume exists on the device.

        Returns:
            bool - True / False if volume exists.
        """
        result = self.api_handler.tm.sys.software.volumes.volume.exists(name=volume_name)

        return result

    def _wait_for_device_reboot(self, volume_name, timeout=600):
        """Waits for the device to be booted into a specified volume.

        Returns:
            bool - True / False if reboot has been successful.
        """
        end_time = time.time() + timeout

        time.sleep(60)

        while time.time() < end_time:
            time.sleep(5)
            try:
                self._reconnect()
                volume = self.api_handler.tm.sys.software.volumes.volume.load(name=volume_name)
                if hasattr(volume, 'active') and volume.active is True:
                    self.uptime
                    self.refresh_active_volume()
                    self.refresh_version()
                    return True
            except Exception:
                pass
        return False

    def _wait_for_image_installed(self, image_name, volume, timeout=900):
        """Waits for the device to install image on a volume.

        Returns:
            bool - True / False if installation has been successful.
        """
        end_time = time.time() + timeout

        while time.time() < end_time:
            time.sleep(20)
            if self.image_installed(image_name=image_name, volume=volume):
                self.uptime
                self.refresh_active_volume()
                self.refresh_version()
                return True

        return False

    @property
    def active_volume(self):
        """Gets name of active volume on the device.

        Returns:
            str - name of active volume.
        """
        if self._active_volume is None:
            for _volume in self.volumes:
                if hasattr(_volume, 'active') and _volume.active is True:
                    self._active_volume = _volume.name
                    break

        return self._active_volume

    def backup_running_config(self, filename):
        raise NotImplementedError

    def checkpoint(self, filename):
        raise NotImplementedError

    def close(self):
        pass

    def config(self, command):
        raise NotImplementedError

    def config_list(self, commands):
        raise NotImplementedError

    @property
    def facts(self):
        if self._facts is None:
            self._facts = {
                'uptime': self.uptime,
                'vendor': self.vendor,
                'model': self.model,
                'hostname': self.hostname,
                'fqdn': self.hostname,
                'os_version': self.version,
                'serial_number': self.serial_number,
                'interfaces': self.interfaces,
                'vlans': self.vlans,
                'uptime_string': self._uptime_to_string(self.uptime),
            }

        return self._facts

    @property
    def free_space(self):
        """Provides the free space on the device as an int.
        """
        if self._free_space is None:
            free_space_output = self.api_handler.tm.util.bash.exec_cmd('run', utilCmdArgs='-c "vgdisplay -s --units G"')
            if free_space_output:
                match = re.match('.*\s/\s(\d+\.?\d+) GB free', free_space_output.commandResult)
                if match:
                    self._free_space = float(match.group(1))

        return self._free_space

    def file_copy(self, src, dest=None, **kwargs):
        if dest and not dest.startswith("/shared/images"):
            raise NotImplementedError("Support only for images - destination is always /shared/images")

        self._upload_image(image_filepath=src)

    def file_copy_remote_exists(self, src, dest=None, **kwargs):
        if dest and not dest.startswith("/shared/images"):
            raise NotImplementedError("Support only for images - destination is always /shared/images")

        local_md5sum = self._file_copy_local_md5(filepath=src)
        file_basename = os.path.basename(src)

        if not self._image_match(image_name=file_basename, checksum=local_md5sum):
            return False
        else:
            return True

    def get_boot_options(self):
        return {'active_volume': self.active_volume}

    @property
    def hostname(self):
        """The hostname of the device
        """
        if self._hostname is None:
            self._hostname = self.soap_handler.Management.Device.get_hostname(self.devices)[0]

        return self._hostname

    def image_installed(self, image_name, volume):
        """Checks if image is installed on a specified volume.

        Returns:
            bool - True / False if image installed on a specified volume.
        """
        if not image_name or not volume:
            raise RuntimeError("image_name and volume must be specified")

        image = None

        self.refresh_images()
        for _image in self.images:
            # fullPath = u'BIGIP-11.6.0.0.0.401.iso'
            if _image.fullPath == image_name:
                image = _image

        if image:
            self.refresh_volumes()
            for _volume in self.volumes:
                if (
                        _volume.name == volume and _volume.version == image.version and
                        _volume.basebuild == image.build and _volume.status == 'complete'
                ):
                    return True

        return False

    @property
    def images(self):
        """List of all images on the device.
        """
        if self._images is None:
            self._images = self.api_handler.tm.sys.software.images.get_collection()

        return self._images

    def install_os(self, image_name, **vendor_specifics):
        volume = vendor_specifics.get('volume')
        if volume is None:
            raise RuntimeError("F5 requires the volume to be specified")

        if not self._check_free_space(min_space=6):
            raise RuntimeError("Not enough free space to install OS")

        options = []
        if not self._volume_exists(volume):
            options.append({'create-volume': True})

        self.api_handler.tm.sys.software.images.exec_cmd('install', name=image_name, volume=volume, options=options)

        if not self._wait_for_image_installed(image_name=image_name, volume=volume):
            raise RuntimeError("Installation of {} failed".format(volume))

    @property
    def interfaces(self):
        """List of interfaces on the device.
        """
        if self._interfaces is None:
            self._interfaces = self.soap_handler.Networking.Interfaces.get_list()

        return self._interfaces

    @property
    def model(self):
        if self._model is None:
            self._model = self.soap_handler.System.SystemInfo.get_marketing_name()

        return self._model

    def open(self):
        pass

    def reboot(self, timer=0, volume=None):
        if self.active_volume == volume or volume is None:
            volume_name = None
        else:
            volume_name = volume

        self._reboot_to_volume(volume_name=volume_name)

        if not self._wait_for_device_reboot(volume_name=volume):
            raise RuntimeError("Reboot to volume {} failed".format(volume))

    def refresh_active_volume(self):
        """Refresh cached active volume.
        """
        self._active_volume = None
        return self.active_volume

    def refresh_free_space(self):
        """Refresh cached free space.
        """
        self._free_space = None
        return self.free_space

    def refresh_images(self):
        """Refresh cached images.
        """
        self._images = None
        return self.images

    def refresh_interfaces(self):
        """Refresh cached interfaces.
        """
        self._interfaces = None
        return self.interfaces

    def refresh_version(self):
        """Refresh cached version.
        """
        self._version = None
        return self.version

    def refresh_vlans(self):
        """Refresh cached vlans.
        """
        self._vlans = None
        return self.vlans

    def refresh_volumes(self):
        """Refresh cached volumes.
        """
        self._volumes = None
        return self.volumes

    def rollback(self, checkpoint_file):
        raise NotImplementedError

    def running_config(self):
        raise NotImplementedError

    def save(self, filename=None):
        raise NotImplementedError

    def set_boot_options(self, image_name, **vendor_specifics):
        raise NotImplementedError

    def show(self, command, raw_text=False):
        raise NotImplementedError

    def show_list(self, commands, raw_text=False):
        raise NotImplementedError

    @property
    def serial_number(self):
        """The serial number of the device.
        """
        if self._serial_number is None:
            system_information = self.soap_handler.System.SystemInfo.get_system_information()
            self._serial_number = system_information.get('chassis_serial')

        return self._serial_number

    def startup_config(self):
        raise NotImplementedError

    @property
    def uptime(self):
        """Provides the uptime of the device.

        The uptime is refreshed each time this property is accessed.
        """
        self._uptime = self.soap_handler.System.SystemInfo.get_uptime()
        return self._uptime

    @property
    def version(self):
        """The version of the OS on the device.
        """
        if self._version is None:
            self._version = self.soap_handler.System.SystemInfo.get_version()

        return self._version

    @property
    def vlans(self):
        """The vlans configured on the device.
        """
        if self._vlans is None:
            rd_list = self.soap_handler.Networking.RouteDomainV2.get_list()
            self._vlans = self.soap_handler.Networking.RouteDomainV2.get_vlan(rd_list)

        return self._vlans

    @property
    def volumes(self):
        """List of all volumes on the device.
        """
        if self._volumes is None:
            self._volumes = self.api_handler.tm.sys.software.volumes.get_collection()

        return self._volumes
