##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2017 Christoph Rackwitz <christoph.rackwitz@rwth-aachen.de>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##

'''
Gray Code and rotary encoder PD.
'''

import sigrokdecode as srd
from collections import deque

def bitpack(bits):
	res = 0

	for i,b in enumerate(bits):
		res |= b << i

	return res

def bitunpack(num, minbits=0):
	res = []

	while num or minbits > 0:
		res.append(num & 1)
		num >>= 1
		minbits -= 1

	return tuple(res)

def gray_encode(plain):
	return plain & (plain >> 1)

def gray_decode(gray):
	temp = gray
	temp ^= (temp >> 8)
	temp ^= (temp >> 4)
	temp ^= (temp >> 2)
	temp ^= (temp >> 1)
	return temp


MAX_CHANNELS = 8 # 10 channels causes some weird problems...

class SamplerateError(Exception):
	pass

class ChannelMapError(Exception):
	pass

class Decoder(srd.Decoder):
	api_version = 3
	id = 'graycode'
	name = 'Gray Code'
	longname = 'Gray Code and rotary encoder PD'
	desc = 'Accumulates increments from rotary encoders, provides timing statistics.'
	license = 'gplv2+'

	inputs = ['logic']
	outputs = ['graycode']
	optional_channels = tuple(
		{'id': 'd{}'.format(i), 'name': 'D{}'.format(i), 'desc': 'Data line {}'.format(i)}
		for i in range(MAX_CHANNELS)
	)
	options = (
		{ 'id': 'numchannels', 'desc': 'Number of Channels', 'default': 0 },
		# FIXME: this can be removed once pulseview's has_channel() is fixed

		{ 'id': 'pulses', 'desc': 'Edges per Rotation', 'default': 0 },
		{ 'id': 'avg_period', 'desc': 'Averaging period', 'default': 10 },
	)
	annotations = (
		('phase', 'Phase'),
		('count', 'Count'),
		('time', 'Time'),
		('average', 'Average'),
		('rate', 'Rate'),
		('rpm', 'rpm'),
	)
	annotation_rows = tuple((u,v,(i,)) for i,(u,v) in enumerate(annotations))

	def __init__(self):
		self.num_channels = 0
		self.phase = 0
		self.count = 0
		self.samplerate = None # baserate
		self.last_n = deque()

	def metadata(self, key, value):
		if key == srd.SRD_CONF_SAMPLERATE:
			self.samplerate = value

	def start(self):
		self.out_ann = self.register(srd.OUTPUT_ANN)

	def decode(self):
		if not self.samplerate:
			raise SamplerateError('Cannot decode without samplerate.')

		if self.options['numchannels']:
			self.num_channels = self.options['numchannels']
		else:
			chmask = [self.has_channel(i) for i in range(MAX_CHANNELS)]
			self.num_channels = sum(chmask)
			if chmask != [i < self.num_channels for i in range(MAX_CHANNELS)]:
				raise ChannelMapError("Assigned channels need to be contiguous")

		ENCODER_STEPS = 1 << self.num_channels

		startbits = self.wait()
		curtime = self.samplenum
		
		self.phase = gray_decode(bitpack(startbits[:self.num_channels]))

		while True:
			prevtime = curtime
			bits = self.wait([{i: 'e'} for i in range(self.num_channels)])
			curtime = self.samplenum

			oldcount = self.count
			oldphase = self.phase

			newphase = self.phase = gray_decode(bitpack(bits[:self.num_channels]))

			phasedelta = (newphase - oldphase + (ENCODER_STEPS//2-1)) % ENCODER_STEPS - (ENCODER_STEPS//2-1)

			period = (curtime - prevtime) / self.samplerate / abs(phasedelta or 1)

			self.count += phasedelta

			self.last_n.append(period)
			if len(self.last_n) > self.options['avg_period']:
				self.last_n.popleft()

			self.put(prevtime, curtime, self.out_ann, [0, ["{}".format(oldphase)]])
			self.put(prevtime, curtime, self.out_ann, [1, ["{}".format(oldcount)]])

			self.put(prevtime, curtime, self.out_ann, [2, ["{:.1f} us".format(1e6 * period)]])

			if self.options['avg_period']:
				self.put(prevtime, curtime, self.out_ann, [3, ["{:.1f} us".format(1e6 * sum(self.last_n) / len(self.last_n))]])

			self.put(prevtime, curtime, self.out_ann, [4, ["{:.1f} Hz".format(1 / period)]])

			if self.options['pulses']:
				self.put(prevtime, curtime, self.out_ann, [5, ["{:.1f}".format(60 / period / self.options['pulses'])]])

