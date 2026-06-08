/* Serial CLI + JSON upload protocol (###BEGIN### name / ###END###). */
#pragma once
#include <Arduino.h>

void cliBegin();
void handleSerialInput();   // call every loop()
