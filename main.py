import glob
import sys
import time

import serial

SKIP_SLA = True


def serial_ports():
    if sys.platform.startswith('win'):
        _ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        _ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        _ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')

    result = []
    for port in _ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result


def hex_list_to_str(hex_list):
    return '[ ' + ' '.join(hex_list) + ' ]'


def write_serial(s, data):
    cmd_bytes = bytearray.fromhex(data)
    write_serial_raw(s, cmd_bytes)


def write_serial_raw(s, data):
    sdata = []
    for cmd_byte in data:
        hex_byte = ("{0:02x}".format(cmd_byte))
        sdata.append(hex_byte)
        s.write(bytearray.fromhex(hex_byte))
    print('TX ->', hex_list_to_str(sdata))


def read_serial(s, byte_count):
    ret = []
    for i in range(byte_count):
        ret.append(s.read(1).hex())
    print('RX <-', hex_list_to_str(ret))
    return ret


def try_handshake(s, port):
    print('\nAttempting handshake on', port)
    data = 'a00a5005'
    rdata = ''
    cmd_bytes = bytearray.fromhex(data)
    for cmd_byte in cmd_bytes:
        _data = ("{0:02x}".format(cmd_byte))
        write_serial(s, _data)
        rdata += ''.join(read_serial(s, 1))
    if rdata == '5ff5affa':
        print('Handshake success! Found MTK device at', port)
        return True
    elif rdata == data:
        print('Handshake complete. Warning: device returned input data.')
    else:
        print('Handshake failed! Aborting.')
        sys.exit(0)


def check_preloader(s):
    # CMD_GET_BL_VER
    print('\nChecking preloader version')
    data = 'fe'
    write_serial(s, data)
    if ''.join(read_serial(s, 1)) == data:
        print('Invalid preloader version! BROM connection.')
    else:
        print('Preloader connection. Preloader version check not implemented, aborting.')
        sys.exit(0)


def get_soc_id(s):
    print('\nQuerying SoC ID')
    data = 'e7'
    write_serial(s, data)
    if ''.join(read_serial(s, 1)) == data:
        read_serial(s, 4)
        read_serial(s, 32)
        read_serial(s, 2)
    else:
        print('Get SoC ID failed! Aborting')
        sys.exit(0)


def load_auth_file():
    return open('auth_sv5.auth', 'rb').read()


def send_auth_file(s):
    print('\nLoading and sending auth file')
    data = 'e2'
    write_serial(s, data)
    if ''.join(read_serial(s, 1)) == data:
        data = '000008d0'
        write_serial(s, data)
        if ''.join(read_serial(s, 4)) == data:
            read_serial(s, 2)
            write_serial_raw(s, load_auth_file())
            read_serial(s, 2)
            if ''.join(read_serial(s, 2)) == '0000':
                print('Auth file send success!')
            else:
                print('Failed to send auth file! Aborting.')
                sys.exit(0)
        else:
            print('Bad command! Aborting.')
            sys.exit(0)
    else:
        print('Send Auth File failed! Aborting.')
        sys.exit(0)


def qualify_host(s):
    print('\nQualify Host')
    if SKIP_SLA:
        print('Skipping qualify host! (SLA_Challenge)')
        return
    else:
        data = 'e3'
        write_serial(s, data)
        if ''.join(read_serial(s, 1)) == data:
            read_serial(s, 2)
            read_serial(s, 4)
            ip = read_serial(s, 16)
            data = '00000100'
            write_serial(s, data)
            if ''.join(read_serial(s, 4)) == data:
                read_serial(s, 2)
                write_serial(s, ''.join(ip))
                read_serial(s, 2)


def load_da():
    f = open('MTK_AllInOne_DA_mt6765_mt6785.bin', 'rb')
    f.seek(int("0x39DC", 0))
    return f.read(229376)


def send_da(s):
    print('\nSend DA')
    data = 'd7'
    write_serial(s, data)
    if ''.join(read_serial(s, 1)) == data:
        data = '00200000'
        write_serial(s, data)
        if ''.join(read_serial(s, 4)) != data:
            return
        data = '000361a8'
        write_serial(s, data)
        if ''.join(read_serial(s, 4)) != data:
            return
        data = '00000100'
        write_serial(s, data)
        if ''.join(read_serial(s, 4)) != data:
            return
        read_serial(s, 2)
        ba = load_da()
        for i in range(int(len(ba)/2000)):
            time.sleep(0.01)
            write_serial_raw(s, ba[i*2000:(i+1)*2000])
        read_serial(s, 2)
        read_serial(s, 2)


if __name__ == '__main__':
    print('Listening for ports!')
    abort = Fals
    while not abort:
        time.sleep(1)
        ports = serial_ports()
        if len(ports) > 0:
            print('Got ports:', ports)
            print('Initializing port', ports[0])
            ser = serial.Serial(port=ports[0], baudrate=115200)
            try_handshake(ser, ports[0])
            check_preloader(ser)
            get_soc_id(ser)
            send_auth_file(ser)
            # qualify_host(ser)
            send_da(ser)
            abort = True
