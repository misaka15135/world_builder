"""Current-user Windows DPAPI store; plaintext never leaves the backend API.

No machine-wide flag, environment mutation, third-party package or plaintext
fallback. The complete endpoint is part of both the filename and encrypted data.
"""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from world_builder.agents.contracts import AgentError, canonical, strict_json


class Blob(ctypes.Structure):
    _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]


def protect(data, *, decrypt=False):
    if sys.platform!='win32':raise AgentError('credential.unsupported','本机不支持Windows用户加密；不会以明文保存密钥。')
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    source_buffer=ctypes.create_string_buffer(data)
    source=Blob(len(data),ctypes.cast(source_buffer,ctypes.POINTER(ctypes.c_ubyte)));output=Blob()
    fn=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    fn.restype=wintypes.BOOL
    try:
        if not fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(output)):
            raise AgentError('credential.crypto','无法使用当前Windows用户加密或解密密钥，请重新保存。')
        return ctypes.string_at(output.pbData,output.cbData)
    finally:
        ctypes.memset(source_buffer,0,len(source_buffer))
        if output.pbData:
            ctypes.memset(output.pbData,0,output.cbData)
            kernel.LocalFree(ctypes.cast(output.pbData,ctypes.c_void_p))


class CredentialStore:
    supported=sys.platform=='win32'
    def __init__(self,path):self.root=Path(path).resolve()
    def path(self,endpoint):return self.root/(hashlib.sha256(endpoint.encode('utf-8')).hexdigest()+'.dpapi')
    def get(self,endpoint):
        path=self.path(endpoint)
        if not path.exists():return None
        try:
            if path.stat().st_size>65536:raise ValueError('size')
            entry=strict_json(protect(path.read_bytes(),decrypt=True))
            if entry.get('version')!=1 or entry.get('endpoint')!=endpoint or not isinstance(entry.get('key'),str) or not entry['key']:
                raise ValueError('binding')
            return entry['key']
        except (OSError,ValueError,AgentError):
            raise AgentError('credential.unreadable','本机保存的密钥无法读取，请在设置中重新保存或清除。') from None
    def status(self,endpoint):
        if not self.supported:return {'supported':False,'saved':False}
        try:return {'supported':True,'saved':bool(self.get(endpoint))}
        except AgentError as error:return {'supported':True,'saved':False,'error':str(error)}
    def save(self,endpoint,key):
        encrypted=protect(canonical({'version':1,'endpoint':endpoint,'key':key}))
        self.root.mkdir(parents=True,exist_ok=True)
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root,prefix='pending-',suffix='.dpapi',delete=False) as stream:
                temporary=Path(stream.name);stream.write(encrypted);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,self.path(endpoint))
        except OSError:
            raise AgentError('credential.write','无法保存本机加密密钥；未使用明文回退，请重试。') from None
        finally:
            if temporary and temporary.exists():temporary.unlink()
    def clear(self,endpoint):
        try:self.path(endpoint).unlink(missing_ok=True)
        except OSError:raise AgentError('credential.clear','无法清除本机密钥，请关闭其他实例后重试。') from None
