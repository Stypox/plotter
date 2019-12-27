#!/usr/bin/python3
import serial
ser = serial.Serial('/dev/ttyACM0', 9600)

file = open("arduino.txt", "rb")

print(ser.readline()[:-2].decode("utf8"))
endByte = b"a"

data = open("arduino.txt", "rb").read()

try:
	i = 0
	while i<len(data):
		mode = data[i:i+1]
		x = int.from_bytes(data[i+1:i+3], byteorder="big", signed=True)
		y = int.from_bytes(data[i+3:i+5], byteorder="big", signed=True)
		print(("Sent: %s x%s y%s                        " % (mode.decode("utf8"), x, y))[:30], end = "", flush=True)

		ser.write(data[i:i+5])
		readData = ser.readline()
		print(readData[:-2].decode("utf8"), flush=True)

		i+=5

	ser.write(endByte)
	readData = ser.readline()
	print(readData[:-2].decode("utf8"), flush=True)
	
except KeyboardInterrupt:
	ser.write(endByte)
	readData = ser.readline()[:-2].decode("utf8")
	if (readData != "Completed!"):
		print(readData, flush=True)
		readData = ser.readline()[:-2].decode("utf8")
	print(readData, flush=True)
	print("Interrupted")
