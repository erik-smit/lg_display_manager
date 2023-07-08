from smbus2 import SMBus, i2c_msg
import argparse
import struct
import time
import logging

# 369853 ms  I2C_DeviceWrite( handle=0xfdc42b0, deviceAddress=0x37, sizeToTransfer=5)
# 369853 ms  I2C_DeviceWrite: 51 82 1 c9 75
# 369915 ms  I2C_DeviceRead( handle=0xfdc42b0, deviceAddress=0x37, sizeToTransfer=11)
# 369917 ms  I2C_DeviceRead: 6e 88 2 0 c9 1 ff ff 3 2 7d
# 369977 ms  I2C_DeviceWrite( handle=0xfdc42b0, deviceAddress=0x37, sizeToTransfer=5)
# 369977 ms  I2C_DeviceWrite: 51 82 1 cb 77
#  43788 ms  I2C_DeviceRead( handle=0x1056ad98, deviceAddress=0x37, sizeToTransfer=11)
#  43790 ms  I2C_DeviceRead: 6e 88 2 0 cb 1 ff ff 0 36 48

LG_MONITOR_DDCCI_I2C_ADDR = 0x37

def getAsHex(buffer):
    data = map(lambda value: f"{value:02x}", buffer)
    return " ".join(list(data))

def msg_add_checksum_2(msg):
    sum = 0x6E
    for i in range(0, len(msg)):
        sum ^= msg[i]
    msg += [sum]
    return msg

class LGI2C(object):
    @staticmethod
    def buildChecksum(addr, data):
        # addr is part of checksum bit-shifted left one
        checksum = addr << 1
        for byte in data:
            checksum = checksum ^ byte

        return checksum

    def __init__(self, bus: SMBus):
        self.bus = bus

    #works on my 40WP95C
    def DDC_input_select(self, display):
        self.DDC2AB(0xf4, 0x00, display, 0x26)

    #works on my 40WP95C
    def DDC_F5_System_Reset(self):
        return self.DDC2AB(0xF5, 0x00, 0x00, 0x10)

    #works on my 40WP95C
    def DDC_68_Select_Language(self, language):
        self.DDC2AB(0x68, 0x00, language, 0x00)

    def DDC_CA_GetModelStr(self):
        return self.DDC2AB(0xCA, 0x00, 0x00, 0x26)

    #works on my 40WP95C
    #TODO: replies 8802 0010 0000 6400 64a4 when not on
    def DDC_E7_read_eeprom(self, adh, adl):
        return self.DDC2AB(0xE7, adh, adl, 0x80)

    #works on my 40WP95C
    def read_edid(self):
        buf = [0x00]

        write = i2c_msg.write(0x50, buf)
        read = i2c_msg.read(0x50, 0x82)
        logging.debug(f"write: {getAsHex(buf)}")

        self.bus.i2c_rdwr(write)
        time.sleep(0.15)
        self.bus.i2c_rdwr(read)

        return read

    def DDC2AB(self, opcode, addr, value, readlen):
        SRCADDR_50 = 0x50
        buf = [0x03, opcode, addr, value]

        ddc2buf = [SRCADDR_50, 0x80 | len(buf) ] + buf
        ddc2buf += [LGI2C.buildChecksum(LG_MONITOR_DDCCI_I2C_ADDR, ddc2buf)]
        logging.debug(f"write: {getAsHex(ddc2buf)}")

        write = i2c_msg.write(LG_MONITOR_DDCCI_I2C_ADDR, ddc2buf)
        self.bus.i2c_rdwr(write)
        if readlen == 0:
            return
        
        read = i2c_msg.read(LG_MONITOR_DDCCI_I2C_ADDR, readlen)
        time.sleep(0.5)
        self.bus.i2c_rdwr(read)
        logging.debug(f"read: {getAsHex(read)}")

        return read

def cmd_read_eeprom(args):
    li = LGI2C(SMBus(args.bus))

    for adh in range(0xa0, 0xb0, 0x2):
        print(li.DDC_E7_read_eeprom(adh, 0), end='')
        print(li.DDC_E7_read_eeprom(adh, 0x80), end='')

def cmd_read_edid(args):
    li = LGI2C(SMBus(args.bus))
    edid = li.read_edid()
    print(getAsHex(edid))

def cmd_read_model_str(args):
    li = LGI2C(SMBus(args.bus))
    modelStr = li.DDC_CA_GetModelStr()
    print(str(modelStr))

def cmd_set_language(args):
    li = LGI2C(SMBus(args.bus))
    print(str(li.DDC_68_Select_Language(args.lang)))

def main():
    parser = argparse.ArgumentParser(
        prog="lgddc"
    )

    parser.add_argument('-b', '--bus', type=int, required=True)
    parser.add_argument('-d', '--debug', action="store_true")

    subparser = parser.add_subparsers()
    set_language = subparser.add_parser('set_language')
    set_language.add_argument('lang', type=int)
    set_language.set_defaults(func=cmd_set_language)

    read_model_str = subparser.add_parser('read_model_str')
    read_model_str.set_defaults(func=cmd_read_model_str)

    read_edid = subparser.add_parser('read_edid')
    read_edid.set_defaults(func=cmd_read_edid)

    read_eeprom = subparser.add_parser('read_eeprom')
    read_eeprom.set_defaults(func=cmd_read_eeprom)

    args = parser.parse_args()

    if not 'func' in args:
        parser.print_usage()
        return

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    args.func(args)
    
if __name__ == "__main__":
    main()