#!/usr/bin/env python3
import os
import sys
import numpy as np

v_of_t = lambda t, a: a*t
x_of_t = lambda t, a: 0.5 * a * t**2

t_of_x = lambda x, a: sqrt(2/a) * np.sqrt(x)
v_of_x = lambda x, a: sqrt(2*a) * np.sqrt(x)

t_of_v = lambda v, a: v / a
x_of_v = lambda v, a: x_of_t(t_of_v(v, a), a)

samplerate = 1e-6
vmax = 0.3
amax = 1.0

rampt = t_of_v(vmax, amax)

x = np.hstack([
	x_of_t(np.arange(0, rampt, samplerate), amax),
	2*x_of_v(vmax, amax) - x_of_t(np.arange(rampt, 0, -samplerate), amax),
])

steps = (x / (np.pi * 45e-3) * 20000).astype(np.uint8)
code = steps ^ (steps >> 1)
open("graycode-ramp.dat", "wb").write(code.tostring())
steps &= 0b11
code = steps ^ (steps >> 1)
open("rotary-ramp.dat", "wb").write(code.tostring())


f = 1.0
t = np.arange(0.0, 2.0, samplerate)
x = (127 + 127 * np.sin(2*np.pi * f * t)).round().astype(np.uint8)
code = x ^ (x >> 1)
open("graycode-sin.dat", "wb").write(code.tostring())
x &= 0b11
code = x ^ (x >> 1)
open("rotary-sin.dat", "wb").write(code.tostring())

