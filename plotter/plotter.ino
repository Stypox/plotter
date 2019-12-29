#include <Servo.h>
constexpr int tempo = 4, tempoServo = 50,
	pennaSu = 60, pennaGiu = 43, pennaSuAlta = 150;

constexpr unsigned char move = 'm', write = 'w', end = 'a';

struct Stepper {
	static constexpr bool avanti = false, indietro = true;

	int8_t en[4];
	int8_t currentStep;
	bool direzione;

	Stepper(int8_t en1, int8_t en2, int8_t en3, int8_t en4) :
			en{en1, en2, en3, en4}, currentStep{0}, direzione{avanti} {
		pinMode(en[0], OUTPUT);
		pinMode(en[1], OUTPUT);
		pinMode(en[2], OUTPUT);
		pinMode(en[3], OUTPUT);
	}

	void step() {
		++currentStep;
		if (currentStep == 4) {
			currentStep = 0;
		}

		if (direzione == avanti) {
			digitalWrite(en[0], currentStep == 0);
			digitalWrite(en[1], currentStep == 1);
			digitalWrite(en[2], currentStep == 2);
			digitalWrite(en[3], currentStep == 3);
		} else /* indietro */ {
			digitalWrite(en[0], currentStep == 3);
			digitalWrite(en[1], currentStep == 2);
			digitalWrite(en[2], currentStep == 1);
			digitalWrite(en[3], currentStep == 0);
		}
	}
};

unsigned char readByte() {
	while (!Serial.available()) {}
	return Serial.read();
}

void stepBoth(Stepper& a, Stepper& b, int16_t passi) {
	for(int16_t p = 0; p < passi; ++p) {
		a.step();
		b.step();
		delay(tempo);
	}
}

void setup() {
	Serial.begin(9600);
	Serial.println("Setup");

	Servo servo;
	servo.attach(42);
	Stepper x1{31, 33, 35, 37}, x2{30, 32, 34, 36},
		y1{47, 49, 51, 53}, y2{8, 9, 10, 11};

	auto step = [&](int16_t passix, int16_t passiy) {
		if (passix < 0) {
			x1.direzione = x2.direzione = Stepper::indietro;
			passix = -passix;
		} else {
			x1.direzione = x2.direzione = Stepper::avanti;
		}

		if (passiy < 0) {
			y1.direzione = y2.direzione = Stepper::indietro;
			passiy = -passiy;
		} else {
			y1.direzione = y2.direzione = Stepper::avanti;
		}


		if (passix == 0) {
			stepBoth(y1, y2, passiy);

		} else if (passiy == 0) {
			stepBoth(x1, x2, passix);

		} else if (passix < passiy) {
			int16_t yFatti = 0;
			float yTot = 0.0f;
			float passiYOgniX = static_cast<float>(passiy) / static_cast<float>(passix); // TODO is this ok?

			for(int16_t px = 0; px < passix; ++px) {
				yTot += passiYOgniX;
				int16_t yDaFare = yTot - yFatti;
				yFatti += yDaFare;

				x1.step();
				x2.step();
				delay(tempo);
				stepBoth(y1, y2, yDaFare);
			}

		} else if (passix == passiy) {
			for(int16_t p = 0; p < passix; ++p) {
				x1.step();
				x2.step();
				y1.step();
				y2.step();
				delay(tempo);
			}

		} else /* passix > passiy */{
			int16_t xFatti = 0;
			float xTot = 0.0f;
			float passiXOgniY = static_cast<float>(passix) / static_cast<float>(passiy); // TODO is this ok?

			for(int16_t py = 0; py < passiy; ++py) {
				xTot += passiXOgniY;
				int16_t xDaFare = xTot - xFatti;
				xFatti += xDaFare;

				y1.step();
				y2.step();
				delay(tempo);
				stepBoth(x1, x2, xDaFare);
			}
		}
	};

	bool penna = false;
	servo.write(pennaSuAlta);
	while (!Serial.available()) {}
	servo.write(pennaSu);
	delay(100);
	while (1) {
		char mode = readByte();
		if (mode == write || mode == move) {
			unsigned char a, b, c, d;
			a=readByte();
			b=readByte();
			c=readByte();
			d=readByte();
			int16_t x = (a << 8) | b;
			int16_t y = (c << 8) | d;

			if ((mode == write) != penna) {
				// the pen mode changed
				penna = !penna;
				servo.write(penna ? pennaGiu : pennaSu);
				delay(tempoServo);
			}

			Serial.print(mode == write ? "Write  " : "Move   ");
			Serial.print("X:");
			Serial.print(x);
			Serial.print(" Y:");
			Serial.println(y);

			step(-x, y);
		} else if (mode == end) {
			servo.write(pennaSuAlta);
			Serial.println("Completed!");
		}
	}
}

void loop() {}
