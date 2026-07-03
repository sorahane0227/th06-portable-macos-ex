#pragma once

#include "ZunResult.hpp"
#include "inttypes.hpp"

#include <AudioToolbox/AudioToolbox.h>
#include <CoreMIDI/CoreMIDI.h>
#include <string>
#include <vector>

// MIDI output through Apple's built-in DLS software synthesizer
// or an external CoreMIDI device.

// Enumerate all available MIDI output destinations.
// Returns vector of (device_name, unique_id) pairs.
// ID 0 is reserved for "Built-in DLS Synth".
std::vector<std::pair<std::string, u32>> EnumerateMidiDevices();

struct MidiDevice
{
  public:
    MidiDevice();
    ~MidiDevice();

    ZunResult Close();
    bool OpenDevice(u32 uDeviceId);
    bool SendShortMsg(u8 midiStatus, u8 firstByte, u8 secondByte);
    bool SendLongMsg(const u8 *buf, u32 len);

  private:
    AudioUnit synthUnit;
    AudioUnit outputUnit;
    MIDIClientRef midiClient;
    MIDIPortRef midiOutPort;
    MIDIEndpointRef midiEndpoint;
    bool usingExternalDevice;
    u32 currentDeviceId;
};
