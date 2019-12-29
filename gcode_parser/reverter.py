#!/usr/bin/python3

inp = open("arduino.txt", "rb")
out = open("out.txt", "w")

bytes = inp.read()
 
i = 0
currX = 0
currY = 0
while i < len(bytes):
	mode = bytes[i]
	x = int.from_bytes(bytes[i+1:i+3], byteorder="big", signed=True)
	y = int.from_bytes(bytes[i+3:i+5], byteorder="big", signed=True)
	currX += x
	currY += y

	if mode == 119:
		out.write("G1 X%.4f Y%.4f\n" % (currX, currY))
	else:
		out.write("G0 X%.4f Y%.4f\n" % (currX, currY))

	i+=5
