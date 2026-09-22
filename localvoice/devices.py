"""Vulkan physical indices, deliberately not WMI/CUDA/HIP ordinals."""
import ctypes as c
import ctypes.util
import sys


def gpu_devices():
    if sys.platform == 'darwin':
        return [('auto', 'Apple Metal / Standard-GPU')]
    library = 'vulkan-1.dll' if sys.platform == 'win32' else ctypes.util.find_library('vulkan')
    if not library:
        return []
    try:
        vk = c.CDLL(library)
        class InstanceInfo(c.Structure):
            _fields_ = [('sType', c.c_uint32), ('pNext', c.c_void_p), ('flags', c.c_uint32),
                        ('app', c.c_void_p), ('layerCount', c.c_uint32), ('layers', c.c_void_p),
                        ('extCount', c.c_uint32), ('extensions', c.c_void_p)]
        vk.vkCreateInstance.argtypes = [c.POINTER(InstanceInfo), c.c_void_p, c.POINTER(c.c_void_p)]
        vk.vkCreateInstance.restype = c.c_int
        vk.vkEnumeratePhysicalDevices.argtypes = [c.c_void_p, c.POINTER(c.c_uint32), c.POINTER(c.c_void_p)]
        vk.vkEnumeratePhysicalDevices.restype = c.c_int
        vk.vkGetPhysicalDeviceProperties.argtypes = [c.c_void_p, c.c_void_p]
        vk.vkDestroyInstance.argtypes = [c.c_void_p, c.c_void_p]
        instance = c.c_void_p()
        if vk.vkCreateInstance(c.byref(InstanceInfo(sType=1)), None, c.byref(instance)) != 0:
            return []
        try:
            count = c.c_uint32()
            if vk.vkEnumeratePhysicalDevices(instance, c.byref(count), None) != 0:
                return []
            devices = (c.c_void_p * count.value)()
            if vk.vkEnumeratePhysicalDevices(instance, c.byref(count), devices) != 0:
                return []
            rows = []
            for index, device in enumerate(devices):
                data = c.create_string_buffer(4096)
                vk.vkGetPhysicalDeviceProperties(device, data)
                device_type = int.from_bytes(data.raw[16:20], 'little')
                name = data.raw[20:276].split(b'\0')[0].decode('utf-8', 'replace')
                if device_type in (1, 2):
                    rows.append((f'vulkan:{index}', f'{name} · Vulkan {index}'))
            return rows
        finally:
            vk.vkDestroyInstance(instance, None)
    except (OSError, AttributeError):
        return []
