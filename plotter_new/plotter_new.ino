#include <Stepper.h>
#include <Servo.h>
#include <LiquidCrystal.h>

constexpr unsigned char MOVE = 'm', WRITE = 'w', END = 'a';
constexpr int STEPS = 200, SPEED = 50;
constexpr int PEN_WRITING_DEG = 10, PEN_MOVING_DEG = 50, PEN_UP_DEG = 130;
constexpr int PEN_DELAY_MS = 100;
constexpr int LCD_LINE_COUNT = 2;
constexpr int STEPS_DIAGONAL_AT_ONCE = 20;

void swap(int16_t& a, int16_t& b) {
    int16_t tmp = a;
    a = b;
    b = tmp;
}

unsigned char readByte() {
    while (!Serial.available()) {}
    return Serial.read();
}

int16_t sign(int16_t n) {
    return n >= 0 ? 1 : -1;
}

void setup() {
    Serial.begin(9600);
    Serial.println("Setup");

    Stepper aStepper(STEPS, 2, 3);
    Stepper bStepper(STEPS, 4, 5);
    aStepper.setSpeed(SPEED);
    bStepper.setSpeed(SPEED);

    Servo penServo;
    penServo.attach(6);

    LiquidCrystal lcd(8, 9, 10, 11, 12, 13);
    lcd.begin(16, LCD_LINE_COUNT);
    int lcdLine = 0;
    

    auto stepOld = [&aStepper, &bStepper](int16_t x, int16_t y) {
        int16_t aSteps = abs(x + y), bSteps = abs(x - y);
        int16_t aSign = sign(x + y), bSign = sign(x - y);

        if (aSteps == 0) {
            bStepper.step(bSteps * bSign);

        } else if (bSteps == 0) {
            aStepper.step(aSteps * aSign);

        } else if (aSteps < bSteps) {
            int16_t bDone = 0;
            float bTot = 0.0f;
            float stepsBEveryA = static_cast<float>(bSteps) / static_cast<float>(aSteps);

            for(int16_t aStep = 0; aStep < aSteps; ++aStep) {
                bTot += stepsBEveryA;
                int16_t bToDo = bTot - bDone;
                bDone += bToDo;

                aStepper.step(aSign);
                bStepper.step(bToDo * bSign);
            }

        } else if (aSteps == bSteps) {
            for(int16_t s = 0; s < aSteps; ++s) {
                aStepper.step(aSign);
                bStepper.step(bSign);
            }

        } else /* aSteps > bSteps */ {
            int16_t aDone = 0;
            float aTot = 0.0f;
            float stepsAEveryB = static_cast<float>(aSteps) / static_cast<float>(bSteps);

            for(int16_t bStep = 0; bStep < bSteps; ++bStep) {
                aTot += stepsAEveryB;
                int16_t aToDo = aTot - aDone;
                aDone += aToDo;

                bStepper.step(bSign);
                aStepper.step(aToDo * aSign);
            }
        }
    };

    auto stepSwap = [&stepOld](bool sw, int16_t x, int16_t y) {
        stepOld(sw ? y : x, sw ? x : y);
    };

    auto step2 = [&stepSwap, &stepOld](int16_t x, int16_t y) {
        if (x == 0 || y == 0) {
            stepOld(x, y);
            return;
        }

        bool sw = false;
        if (abs(y) > abs(x)) {
            sw = true;
            swap(x, y);
        }

        int16_t xSign = sign(x), ySign = sign(y);
        int16_t xAbs = abs(x), yAbs = abs(y);

        int xDone = 0;
        int16_t yDone = 0;
        float yTot = 0.0f;
        float stepsYEveryX = ((float) yAbs) / (xAbs);
        
        while (xDone + STEPS_DIAGONAL_AT_ONCE < xAbs) {
            yTot += stepsYEveryX * STEPS_DIAGONAL_AT_ONCE;
            int16_t yToDo = yTot - yDone;

            yDone += yToDo;
            xDone += STEPS_DIAGONAL_AT_ONCE;
            
            stepSwap(sw, STEPS_DIAGONAL_AT_ONCE * xSign, 0);
            stepSwap(sw, 0, yToDo * ySign);
        }
        stepSwap(sw, (xAbs - xDone) * xSign, 0);
        stepSwap(sw, 0, (yAbs - yDone) * ySign);
    };

    auto setPenDegrees = [&penServo](const int deg) {
        penServo.write(deg);
        delay(PEN_DELAY_MS);
    };

    auto logMsg = [&lcd](const char* msg) {
        Serial.print(msg);
        lcd.print(msg);
    };

    auto loglnMsg = [&lcd, &lcdLine](const char* msg) {
        Serial.println(msg);
        lcd.print(msg);

        ++lcdLine;
        lcdLine %= LCD_LINE_COUNT;
        lcd.setCursor(0, lcdLine);
        lcd.print("                ");
        lcd.setCursor(0, lcdLine);
    };

    auto logNum = [&lcd](const int msg) {
        Serial.print(msg);
        lcd.print(msg);
    };


    bool penIsWriting = false;
    setPenDegrees(PEN_UP_DEG);
    while (1) {
        char mode = readByte();
        if (mode == WRITE || mode == MOVE) {
            unsigned char a, b, c, d;
            a = readByte();
            b = readByte();
            c = readByte();
            d = readByte();
            int16_t x = (a << 8) | b;
            int16_t y = (c << 8) | d;

            bool newPenIsWriting = (mode == WRITE);
            if (newPenIsWriting != penIsWriting) {
                // the pen mode changed, move it accordingly
                penIsWriting = newPenIsWriting;
                setPenDegrees(penIsWriting ? PEN_WRITING_DEG : PEN_MOVING_DEG);
            }

            logMsg(penIsWriting ? "w x=" : "m x=");
            logNum(x);
            logMsg(" y=");
            logNum(y);

            step2(-x, y);

            loglnMsg("*");

        } else if (mode == END) {
            penIsWriting = false;
            setPenDegrees(PEN_UP_DEG);
            loglnMsg("Completed!");
        }
        /*
        switch(readByte()) {
        case 'w':
            step2(100, 0);
            break;
        case 'a':
            step2(0, -100);
            break;
        case 's':
            step2(-100, 0);
            break;
        case 'd':
            step2(0, 100);
            break;
        case 'q':
            step2(100, -100);
            break;
        case 'e':
            step2(100, 100);
            break;
        case 'x':
            step2(-100, 100);
            break;
        case 'z':
            step2(-100, -100);
            break;
        }
        Serial.println("\n");*/
    }
}

void loop() {}
