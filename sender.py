#!/usr/bin/python3

import argparse
import serial

endByte = b"a"
serialLogLabel = "[info from serial]"


def _log_nothing(*args, **kwargs):
	pass

def sendData(data, serialPort, baudRate, simulate=False, log=_log_nothing):
	if simulate:
		log(serialLogLabel, "Setup")
	else:
		ser = serial.Serial(serialPort, baudRate)
		log(serialLogLabel, ser.readline()[:-2].decode("utf8"))

	try:
		i = 0
		while i < len(data):
			mode = data[i:i+1]
			x = int.from_bytes(data[i+1:i+3], byteorder="big", signed=True)
			y = int.from_bytes(data[i+3:i+5], byteorder="big", signed=True)
			log(f"[info] Sent: {repr(mode)[2:-1]:<2} x={x:>5} y={y:>5}")

			if not simulate:
				ser.write(data[i:i+5])
				readData = ser.readline()
				log(serialLogLabel, readData[:-2].decode("utf8"))

			i+=5

	except KeyboardInterrupt:
		log("[info] Sending interrupted by user")
	finally:
		if simulate:
			log("[info] Completed!")
		else:
			ser.write(endByte)
			readData = ser.readline()[:-2].decode("utf8")
			log(serialLogLabel, readData)
			if (readData != "Completed!"):
				log(serialLogLabel, readData)
				readData = ser.readline()[:-2].decode("utf8")
	





def parseArgs(namespace):
	argParser = argparse.ArgumentParser(fromfile_prefix_chars="@",
		description="Send binary data to a plotter using a serial connection")

	ioGroup = argParser.add_argument_group("Input/output options")
	ioGroup.add_argument("-i", "--input", type=argparse.FileType('rb'), required=True, metavar="FILE",
		help="Binary file from which to read the raw data to send to the plotter")
	ioGroup.add_argument("-l", "--log", type=argparse.FileType('w'), required=False, metavar="FILE",
		help="File in which to save logs, comments and warnings")

	connGroup = argParser.add_argument_group("Plotter connectivity options")
	connGroup.add_argument("--simulate", action="store_true",
		help="Simulate sending data to the plotter without really opening a connection. Useful with logging enabled to debug the commands sent.")
	connGroup.add_argument("--port", "--serial-port", type=str, metavar="PORT", dest="serial_port",
		help="The serial port the plotter is connected to (required unless there is --simulate)")
	connGroup.add_argument("--baud", "--baud-rate", type=int, metavar="RATE", dest="baud_rate",
		help="The baud rate to use for the connection with the plotter. It has to be equal to the plotter baud rate. (required unless there is --simulate)")

	argParser.parse_args(namespace=namespace)


	if not namespace.simulate:
		if namespace.serial_port is None:
			argParser.error(f"--serial-port is required unless there is --simulate")
		if namespace.baud_rate is None:
			argParser.error(f"--baud-rate is required unless there is --simulate")

class Args:
	pass

def main():
	parseArgs(Args)

	def log(*args, **kwargs):
		if Args.log is not None:
			kwargs["flush"] = True
			print(*args, **kwargs, file=Args.log)
	
	data = Args.input.read()
	sendData(data, Args.serial_port, Args.baud_rate, Args.simulate, log=log)


if __name__ == "__main__":
	main()