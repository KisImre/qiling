#!/usr/bin/env python3
# 
# Cross Platform and Multi Architecture Advanced Binary Emulation Framework
#

"""
This module is intended for general purpose functions that are only used in qiling.os
"""

from typing import MutableMapping, Union, Sequence, MutableSequence, Tuple
from uuid import UUID

from qiling import Qiling
from qiling.const import QL_VERBOSE

class QlOsUtils:

    ELLIPSIS_PREF = r'__qlva_'

    def __init__(self, ql: Qiling):
        self.ql = ql

    @staticmethod
    def read_string(ql: Qiling, address: int, terminator: bytes) -> str:
        result = bytearray()
        charlen = len(terminator)

        char = ql.mem.read(address, charlen)

        while char != terminator:
            address += charlen
            result += char
            char = ql.mem.read(address, charlen)

        return result.decode(errors="ignore")

    def read_wstring(self, address: int) -> str:
        s = QlOsUtils.read_string(self.ql, address, b'\x00\x00')

        # We need to remove \x00 inside the string. Compares do not work otherwise
        s = s.replace("\x00", "")
        self.ql.os.stats.log_string(s)

        return s

    def read_cstring(self, address: int) -> str:
        s = QlOsUtils.read_string(self.ql, address, b'\x00')

        self.ql.os.stats.log_string(s)

        return s

    def read_guid(self, address: int) -> UUID:
        raw_guid = self.ql.mem.read(address, 16)

        return UUID(bytes_le=bytes(raw_guid))

    @staticmethod
    def stringify(s: str) -> str:
        """Decorate a string with quotation marks.
        """

        return f'"{repr(s)[1:-1]}"'

    def print_function(self, address: int, fname: str, pargs: Sequence[Tuple[str, str]], ret: Union[int, str, None], passthru: bool):
        '''Print out function invocation detais.

        Args:
            address: fucntion address
            fnamr: function name
            pargs: processed args list: a sequence of 2-tuples consisting of arg names paired to string representation of arg values
            ret: function return value, or None if no such value
            passthru: whether this is a passthrough invocation (no frame unwinding)
        '''

        if fname.startswith('hook_'):
            fname = fname[5:]

        def __assign_arg(name: str, value: str) -> str:
            # ignore arg names generated by variadric functions
            if name.startswith(QlOsUtils.ELLIPSIS_PREF):
                name = ''

            return f'{name} = {value}' if name else f'{value}'

        # arguments list
        fargs = ', '.join(__assign_arg(name, value) for name, value in pargs)

        if type(ret) is int:
            ret = f'{ret:#x}'

        # optional prefixes and suffixes
        fret = f' = {ret}' if ret is not None else ''
        fpass = f' (PASSTHRU)' if passthru else ''
        faddr = f'{address:#0{self.ql.arch.bits // 4 + 2}x}: ' if self.ql.verbose >= QL_VERBOSE.DEBUG else ''

        log = f'{faddr}{fname}({fargs}){fret}{fpass}'

        if self.ql.verbose >= QL_VERBOSE.DEBUG:
            self.ql.log.debug(log)
        else:
            self.ql.log.info(log)

    def __common_printf(self, format: str, args: MutableSequence, wstring: bool):
        fmtstr = format.split("%")[1:]
        read_string = self.read_wstring if wstring else self.read_cstring

        for i, f in enumerate(fmtstr):
            if f.startswith("s"):
                args[i] = read_string(args[i])

        out = format.replace(r'%llx', r'%x')
        out = out.replace(r'%p', r'%#x')

        return out % tuple(args)

    def va_list(self, format: str, ptr: int) -> MutableSequence[int]:
        count = format.count("%")

        return [self.ql.mem.read_ptr(ptr + i * self.ql.arch.pointersize) for i in range(count)]

    def sprintf(self, buff: int, format: str, args: MutableSequence, wstring: bool = False) -> int:
        out = self.__common_printf(format, args, wstring)
        enc = 'utf-16le' if wstring else 'utf-8'

        self.ql.mem.write(buff, (out + '\x00').encode(enc))

        return len(out)

    def printf(self, format: str, args: MutableSequence, wstring: bool = False) -> int:
        out = self.__common_printf(format, args, wstring)
        enc = 'utf-8'

        self.ql.os.stdout.write(out.encode(enc))

        return len(out)

    def update_ellipsis(self, params: MutableMapping, args: Sequence) -> None:
        params.update((f'{QlOsUtils.ELLIPSIS_PREF}{i}', a) for i, a in enumerate(args))
