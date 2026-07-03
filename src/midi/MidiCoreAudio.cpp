#include "MidiCoreAudio.hpp"
#include "utils.hpp"

#include <CoreMIDI/CoreMIDI.h>
#include <unistd.h>

static AudioUnit CreateUnit(OSType type, OSType subType)
{
    AudioComponentDescription desc = {};
    desc.componentType = type;
    desc.componentSubType = subType;
    desc.componentManufacturer = kAudioUnitManufacturer_Apple;

    AudioComponent component = AudioComponentFindNext(NULL, &desc);
    if (component == NULL)
    {
        return NULL;
    }

    AudioUnit unit = NULL;
    if (AudioComponentInstanceNew(component, &unit) != noErr)
    {
        return NULL;
    }

    return unit;
}

std::vector<std::pair<std::string, u32>> EnumerateMidiDevices()
{
    std::vector<std::pair<std::string, u32>> devices;

    // ID 0 = built-in DLS synthesizer (always available on macOS)
    devices.push_back({"Built-in DLS Synth", 0});

    // Walk the full MIDI device tree to find all output destinations.
    // This catches IAC Driver buses, USB MIDI interfaces, network MIDI, etc.
    ItemCount numDevices = MIDIGetNumberOfDevices();
    for (ItemCount i = 0; i < numDevices; i++)
    {
        MIDIDeviceRef device = MIDIGetDevice(i);
        if (device == 0)
            continue;

        ItemCount numEntities = MIDIDeviceGetNumberOfEntities(device);
        for (ItemCount e = 0; e < numEntities; e++)
        {
            MIDIEntityRef entity = MIDIDeviceGetEntity(device, e);
            if (entity == 0)
                continue;

            ItemCount numDestinations = MIDIEntityGetNumberOfDestinations(entity);
            for (ItemCount d = 0; d < numDestinations; d++)
            {
                MIDIEndpointRef endpoint = MIDIEntityGetDestination(entity, d);
                if (endpoint == 0)
                    continue;

                // Build name: "Device Name: Endpoint Name" or just endpoint name
                CFStringRef devNameCF = NULL;
                MIDIObjectGetStringProperty(device, kMIDIPropertyName, &devNameCF);
                CFStringRef epNameCF = NULL;
                MIDIObjectGetStringProperty(endpoint, kMIDIPropertyName, &epNameCF);

                char nameBuf[512];
                if (devNameCF && epNameCF)
                {
                    char devName[256], epName[256];
                    CFStringGetCString(devNameCF, devName, sizeof(devName), kCFStringEncodingUTF8);
                    CFStringGetCString(epNameCF, epName, sizeof(epName), kCFStringEncodingUTF8);
                    // If entity/endpoint name is the same as device name, just use one
                    if (strcmp(devName, epName) == 0)
                        snprintf(nameBuf, sizeof(nameBuf), "%s", epName);
                    else
                        snprintf(nameBuf, sizeof(nameBuf), "%s - %s", devName, epName);
                }
                else if (epNameCF)
                {
                    CFStringGetCString(epNameCF, nameBuf, sizeof(nameBuf), kCFStringEncodingUTF8);
                }
                else if (devNameCF)
                {
                    CFStringGetCString(devNameCF, nameBuf, sizeof(nameBuf), kCFStringEncodingUTF8);
                }
                else
                {
                    snprintf(nameBuf, sizeof(nameBuf), "MIDI Device %d:%d:%d", i, e, d);
                }

                if (devNameCF) CFRelease(devNameCF);
                if (epNameCF) CFRelease(epNameCF);

                // Get unique ID
                SInt32 uniqueId = 0;
                MIDIObjectGetIntegerProperty(endpoint, kMIDIPropertyUniqueID, &uniqueId);

                devices.push_back({std::string(nameBuf), (u32)uniqueId});
            }
        }
    }

    // Also check standalone destinations not tied to a device entity
    ItemCount numDestinations = MIDIGetNumberOfDestinations();
    for (ItemCount i = 0; i < numDestinations; i++)
    {
        MIDIEndpointRef endpoint = MIDIGetDestination(i);
        if (endpoint == 0)
            continue;

        SInt32 uniqueId = 0;
        MIDIObjectGetIntegerProperty(endpoint, kMIDIPropertyUniqueID, &uniqueId);

        // Check if this endpoint was already added via device walk
        bool alreadyAdded = false;
        for (const auto &dev : devices)
        {
            if (dev.second == (u32)uniqueId)
            {
                alreadyAdded = true;
                break;
            }
        }
        if (alreadyAdded)
            continue;

        CFStringRef nameCF = NULL;
        MIDIObjectGetStringProperty(endpoint, kMIDIPropertyName, &nameCF);
        if (nameCF == NULL)
            continue;

        char nameBuf[256];
        CFStringGetCString(nameCF, nameBuf, sizeof(nameBuf), kCFStringEncodingUTF8);
        CFRelease(nameCF);

        devices.push_back({std::string(nameBuf), (u32)uniqueId});
    }

    return devices;
}

MidiDevice::MidiDevice()
{
    this->synthUnit = NULL;
    this->outputUnit = NULL;
    this->midiClient = 0;
    this->midiOutPort = 0;
    this->midiEndpoint = 0;
    this->usingExternalDevice = false;
    this->currentDeviceId = 0xFFFFFFFF;
}

MidiDevice::~MidiDevice()
{
    this->Close();
}

bool MidiDevice::OpenDevice(u32 uDeviceId)
{
    // If already open and using the same device, just keep it — no need to close/reopen.
    if ((this->usingExternalDevice || this->synthUnit != NULL) && this->currentDeviceId == uDeviceId)
    {
        return true;
    }

    // Close any previously open device (different device or first open)
    this->Close();
    this->currentDeviceId = uDeviceId;

    // Device ID 0 = built-in DLS synth
    if (uDeviceId == 0)
    {
        this->usingExternalDevice = false;

        this->synthUnit = CreateUnit(kAudioUnitType_MusicDevice, kAudioUnitSubType_DLSSynth);
        if (this->synthUnit == NULL)
        {
            utils::DebugPrint2("error : couldn't create the DLS synth audio unit\n");
            this->Close();
            return false;
        }

        this->outputUnit = CreateUnit(kAudioUnitType_Output, kAudioUnitSubType_DefaultOutput);
        if (this->outputUnit == NULL)
        {
            utils::DebugPrint2("error : couldn't create the default output audio unit\n");
            this->Close();
            return false;
        }

        AudioUnitConnection connection;
        connection.sourceAudioUnit = this->synthUnit;
        connection.sourceOutputNumber = 0;
        connection.destInputNumber = 0;
        if (AudioUnitSetProperty(this->outputUnit, kAudioUnitProperty_MakeConnection, kAudioUnitScope_Input, 0,
                                 &connection, sizeof(connection)) != noErr)
        {
            utils::DebugPrint2("error : couldn't connect the synth to the audio output\n");
            this->Close();
            return false;
        }

        if (AudioUnitInitialize(this->synthUnit) != noErr || AudioUnitInitialize(this->outputUnit) != noErr ||
            AudioOutputUnitStart(this->outputUnit) != noErr)
        {
            utils::DebugPrint2("error : couldn't start the audio output\n");
            this->Close();
            return false;
        }

        utils::DebugPrint2("Playing midi through the DLS software synthesizer\n");
        return true;
    }

    // External CoreMIDI device
    this->usingExternalDevice = true;

    // Create MIDI client
    CFStringRef clientName = CFSTR("th06-portable");
    if (MIDIClientCreate(clientName, NULL, NULL, &this->midiClient) != noErr)
    {
        utils::DebugPrint2("error : couldn't create MIDI client\n");
        this->Close();
        return false;
    }

    // Create output port
    if (MIDIOutputPortCreate(this->midiClient, CFSTR("Output"), &this->midiOutPort) != noErr)
    {
        utils::DebugPrint2("error : couldn't create MIDI output port\n");
        this->Close();
        return false;
    }

    // Find the endpoint with the matching unique ID
    ItemCount numDest = MIDIGetNumberOfDestinations();
    for (ItemCount i = 0; i < numDest; i++)
    {
        MIDIEndpointRef ep = MIDIGetDestination(i);
        SInt32 uniqueId = 0;
        MIDIObjectGetIntegerProperty(ep, kMIDIPropertyUniqueID, &uniqueId);
        if ((u32)uniqueId == uDeviceId)
        {
            this->midiEndpoint = ep;
            break;
        }
    }

    if (this->midiEndpoint == 0)
    {
        utils::DebugPrint2("error : MIDI device with ID %u not found, falling back to DLS\n", uDeviceId);
        this->Close();
        return this->OpenDevice(0);
    }

    // Get the device name for logging
    CFStringRef nameCF = NULL;
    MIDIObjectGetStringProperty(this->midiEndpoint, kMIDIPropertyName, &nameCF);
    char nameBuf[256] = "Unknown";
    if (nameCF)
    {
        CFStringGetCString(nameCF, nameBuf, sizeof(nameBuf), kCFStringEncodingUTF8);
        CFRelease(nameCF);
    }

    utils::DebugPrint2("Playing midi through external device: %s (ID %u)\n", nameBuf, uDeviceId);
    return true;
}

ZunResult MidiDevice::Close()
{
    if (this->usingExternalDevice && this->midiOutPort != 0 && this->midiEndpoint != 0)
    {
        // Send All Notes Off (CC 123) + All Sound Off (CC 120) on all channels.
        // Using individual MIDISend calls to ensure reliable delivery.
        for (u8 channel = 0; channel < 16; channel++)
        {
            u8 msg1[3] = { (u8)(0xB0 | channel), 123, 0 };  // All Notes Off
            u8 msg2[3] = { (u8)(0xB0 | channel), 120, 0 };  // All Sound Off

            MIDIPacketList pktList;
            MIDIPacket *pkt = MIDIPacketListInit(&pktList);
            MIDIPacketListAdd(&pktList, sizeof(pktList), pkt, 0, 3, msg1);
            MIDISend(this->midiOutPort, this->midiEndpoint, &pktList);

            pkt = MIDIPacketListInit(&pktList);
            MIDIPacketListAdd(&pktList, sizeof(pktList), pkt, 0, 3, msg2);
            MIDISend(this->midiOutPort, this->midiEndpoint, &pktList);
        }
        // Brief delay to let the panic messages flush through IAC before disposing the port
        usleep(50000);  // 50ms
        utils::DebugPrint2("MIDI: panic sent (CC123+CC120 × 16ch)\n");
    }

    if (this->usingExternalDevice)
    {
        if (this->midiOutPort != 0)
        {
            MIDIPortDispose(this->midiOutPort);
            this->midiOutPort = 0;
        }
        if (this->midiClient != 0)
        {
            MIDIClientDispose(this->midiClient);
            this->midiClient = 0;
        }
        this->midiEndpoint = 0;
        this->usingExternalDevice = false;
        return ZUN_SUCCESS;
    }

    if (this->synthUnit == NULL && this->outputUnit == NULL)
    {
        return ZUN_ERROR;
    }

    // Send All Notes Off via DLS synth before stopping
    if (this->synthUnit != NULL)
    {
        for (u8 channel = 0; channel < 16; channel++)
        {
            MusicDeviceMIDIEvent(this->synthUnit, 0xB0 | channel, 123, 0, 0);
        }
    }

    if (this->outputUnit != NULL)
    {
        AudioOutputUnitStop(this->outputUnit);
        AudioUnitUninitialize(this->outputUnit);
        AudioComponentInstanceDispose(this->outputUnit);
        this->outputUnit = NULL;
    }

    if (this->synthUnit != NULL)
    {
        AudioUnitUninitialize(this->synthUnit);
        AudioComponentInstanceDispose(this->synthUnit);
        this->synthUnit = NULL;
    }

    return ZUN_SUCCESS;
}

bool MidiDevice::SendShortMsg(u8 midiStatus, u8 firstByte, u8 secondByte)
{
    if (this->usingExternalDevice)
    {
        if (this->midiOutPort == 0 || this->midiEndpoint == 0)
            return false;

        MIDIPacketList packetList;
        MIDIPacket *packet = MIDIPacketListInit(&packetList);

        u8 data[3] = {midiStatus, firstByte, secondByte};
        // Calculate actual message length (1, 2, or 3 bytes depending on status)
        u32 len = 3;
        if ((midiStatus & 0xF0) == 0xC0 || (midiStatus & 0xF0) == 0xD0)
            len = 2;

        packet = MIDIPacketListAdd(&packetList, sizeof(packetList), packet, 0, len, data);
        if (packet == NULL)
        {
            utils::DebugPrint2("MIDI: PacketListAdd failed %02X %02X %02X\n", midiStatus, firstByte, secondByte);
            return false;
        }
        OSStatus st = MIDISend(this->midiOutPort, this->midiEndpoint, &packetList);
        if (st != noErr)
        {
            utils::DebugPrint2("MIDI: MIDISend err %d for %02X\n", (int)st, midiStatus);
            return false;
        }
        return true;
    }

    if (this->synthUnit == NULL)
    {
        return true;
    }

    return MusicDeviceMIDIEvent(this->synthUnit, midiStatus, firstByte, secondByte, 0) == noErr;
}

bool MidiDevice::SendLongMsg(const u8 *buf, u32 len)
{
    if (this->usingExternalDevice)
    {
        if (this->midiOutPort == 0 || this->midiEndpoint == 0)
            return false;

        // Build a MIDIPacketList large enough for the SysEx data
        size_t packetListSize = sizeof(MIDIPacketList) + len;
        MIDIPacketList *packetList = (MIDIPacketList *)malloc(packetListSize);
        if (packetList == NULL)
            return false;

        MIDIPacket *packet = MIDIPacketListInit(packetList);
        packet = MIDIPacketListAdd(packetList, packetListSize, packet, 0, len, buf);
        bool result = MIDISend(this->midiOutPort, this->midiEndpoint, packetList) == noErr;
        free(packetList);
        return result;
    }

    if (this->synthUnit == NULL)
    {
        return true;
    }

    return MusicDeviceSysEx(this->synthUnit, buf, len) == noErr;
}
