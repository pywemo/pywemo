"""WeMo service types.

Do not hand edit. This file is automatically generated. Any manual changes
will be erased the next time it is re-generated.

To regenerate this file, run:
  scripts/generate_wemo_services.py > \
      pywemo/ouimeaux_device/api/wemo_services.pyi
"""

from typing import Callable

UPnPMethod = Callable[..., dict[str, str]]

class Service_WiFiSetup:
    CloseSetup: UPnPMethod
    ConnectHomeNetwork: UPnPMethod
    GetApList: UPnPMethod
    GetNetworkList: UPnPMethod
    GetNetworkStatus: UPnPMethod
    StopPair: UPnPMethod

class Service_basicevent:
    Calibrate: UPnPMethod
    ChangeDeviceIcon: UPnPMethod
    ChangeFriendlyName: UPnPMethod
    CheckResetButtonState: UPnPMethod
    ConfigureDimmingRange: UPnPMethod
    ConfigureHushMode: UPnPMethod
    ConfigureNightMode: UPnPMethod
    ControlCloudUpload: UPnPMethod
    GetBinaryState: UPnPMethod
    GetCrockpotState: UPnPMethod
    GetDeviceIcon: UPnPMethod
    GetDeviceId: UPnPMethod
    GetEnforceSecurity: UPnPMethod
    GetFriendlyName: UPnPMethod
    GetGPIO: UPnPMethod
    GetHKSetupInfo: UPnPMethod
    GetHomeId: UPnPMethod
    GetHomeInfo: UPnPMethod
    GetIconURL: UPnPMethod
    GetIconVersion: UPnPMethod
    GetInsightHomeSettings: UPnPMethod
    GetJardenStatus: UPnPMethod
    GetLogFileURL: UPnPMethod
    GetMacAddr: UPnPMethod
    GetNightLightStatus: UPnPMethod
    GetNightModeConfiguration: UPnPMethod
    GetPluginUDN: UPnPMethod
    GetRuleOverrideStatus: UPnPMethod
    GetSerialNo: UPnPMethod
    GetServerEnvironment: UPnPMethod
    GetSetupDoneStatus: UPnPMethod
    GetSignalStrength: UPnPMethod
    GetSimulatedRuleData: UPnPMethod
    GetSmartDevInfo: UPnPMethod
    GetWatchdogFile: UPnPMethod
    NotifyManualToggle: UPnPMethod
    ReSetup: UPnPMethod
    SetAwayRuleTask: UPnPMethod
    SetBinaryState: UPnPMethod
    SetBulbType: UPnPMethod
    SetCrockpotState: UPnPMethod
    SetDeviceId: UPnPMethod
    SetEnforceSecurity: UPnPMethod
    SetGPIO: UPnPMethod
    SetHomeId: UPnPMethod
    SetInsightHomeSettings: UPnPMethod
    SetJardenStatus: UPnPMethod
    SetLogLevelOption: UPnPMethod
    SetMultiState: UPnPMethod
    SetNightLightStatus: UPnPMethod
    SetServerEnvironment: UPnPMethod
    SetSetupDoneStatus: UPnPMethod
    SetSmartDevInfo: UPnPMethod
    ShareHWInfo: UPnPMethod
    SimulateLongPress: UPnPMethod
    SimulateOverTemp: UPnPMethod
    StartIperf: UPnPMethod
    StopIperf: UPnPMethod
    TestLEDs: UPnPMethod
    UpdateInsightHomeSettings: UPnPMethod
    getHKSetupState: UPnPMethod
    identifyDevice: UPnPMethod
    removeHomekitData: UPnPMethod
    setAutoFWUpdate: UPnPMethod
    setDummyMode: UPnPMethod
    setHKSetupState: UPnPMethod

class Service_bridge:
    AddDevice: UPnPMethod
    AddDeviceName: UPnPMethod
    CloseNetwork: UPnPMethod
    CreateGroup: UPnPMethod
    DeleteDataStores: UPnPMethod
    DeleteGroup: UPnPMethod
    GetCapabilityProfileIDList: UPnPMethod
    GetCapabilityProfileList: UPnPMethod
    GetDataStores: UPnPMethod
    GetDeviceCapabilities: UPnPMethod
    GetDeviceStatus: UPnPMethod
    GetEndDevices: UPnPMethod
    GetEndDevicesWithStatus: UPnPMethod
    GetGroups: UPnPMethod
    IdentifyDevice: UPnPMethod
    OpenNetwork: UPnPMethod
    QAControl: UPnPMethod
    RemoveDevice: UPnPMethod
    ScanZigbeeJoin: UPnPMethod
    SetDataStores: UPnPMethod
    SetDeviceName: UPnPMethod
    SetDeviceNames: UPnPMethod
    SetDeviceStatus: UPnPMethod
    SetZigbeeMode: UPnPMethod
    UpgradeSubDeviceFirmware: UPnPMethod

class Service_deviceevent:
    GetAttributeList: UPnPMethod
    GetAttributes: UPnPMethod
    GetBlobStorage: UPnPMethod
    SetAttributes: UPnPMethod
    SetBlobStorage: UPnPMethod

class Service_deviceinfo:
    CloseInstaAP: UPnPMethod
    GetAutoFwUpdateVar: UPnPMethod
    GetConfigureState: UPnPMethod
    GetDeviceInformation: UPnPMethod
    GetInformation: UPnPMethod
    GetRouterInformation: UPnPMethod
    InstaConnectHomeNetwork: UPnPMethod
    InstaRemoteAccess: UPnPMethod
    OpenInstaAP: UPnPMethod
    SetAutoFwUpdateVar: UPnPMethod
    UpdateBridgeList: UPnPMethod

class Service_firmwareupdate:
    GetFirmwareVersion: UPnPMethod
    UpdateFirmware: UPnPMethod

class Service_insight:
    GetDataExportInfo: UPnPMethod
    GetInSBYSince: UPnPMethod
    GetInsightInfo: UPnPMethod
    GetInsightParams: UPnPMethod
    GetONFor: UPnPMethod
    GetPower: UPnPMethod
    GetPowerThreshold: UPnPMethod
    GetTodayKWH: UPnPMethod
    GetTodayONTime: UPnPMethod
    GetTodaySBYTime: UPnPMethod
    ResetPowerThreshold: UPnPMethod
    ScheduleDataExport: UPnPMethod
    SetAutoPowerThreshold: UPnPMethod
    SetPowerThreshold: UPnPMethod

class Service_manufacture:
    GetManufactureData: UPnPMethod

class Service_metainfo:
    GetExtMetaInfo: UPnPMethod
    GetMetaInfo: UPnPMethod

class Service_remoteaccess:
    RemoteAccess: UPnPMethod

class Service_rules:
    DeleteRuleID: UPnPMethod
    DeleteWeeklyCalendar: UPnPMethod
    EditWeeklycalendar: UPnPMethod
    FetchRules: UPnPMethod
    GetRules: UPnPMethod
    GetRulesDBPath: UPnPMethod
    GetRulesDBVersion: UPnPMethod
    GetTemplates: UPnPMethod
    SetRuleID: UPnPMethod
    SetRules: UPnPMethod
    SetRulesDBVersion: UPnPMethod
    SetTemplates: UPnPMethod
    SimulatedRuleData: UPnPMethod
    StoreRules: UPnPMethod
    UpdateWeeklyCalendar: UPnPMethod

class Service_smartsetup:
    GetRegistrationData: UPnPMethod
    GetRegistrationStatus: UPnPMethod
    PairAndRegister: UPnPMethod

class Service_timesync:
    GetDeviceTime: UPnPMethod
    GetTime: UPnPMethod
    TimeSync: UPnPMethod

class WeMoServiceTypesMixin:
    WiFiSetup: Service_WiFiSetup
    basicevent: Service_basicevent
    bridge: Service_bridge
    deviceevent: Service_deviceevent
    deviceinfo: Service_deviceinfo
    firmwareupdate: Service_firmwareupdate
    insight: Service_insight
    manufacture: Service_manufacture
    metainfo: Service_metainfo
    remoteaccess: Service_remoteaccess
    rules: Service_rules
    smartsetup: Service_smartsetup
    timesync: Service_timesync

class WeMoAllActionsMixin(
    Service_WiFiSetup,
    Service_basicevent,
    Service_bridge,
    Service_deviceevent,
    Service_deviceinfo,
    Service_firmwareupdate,
    Service_insight,
    Service_manufacture,
    Service_metainfo,
    Service_remoteaccess,
    Service_rules,
    Service_smartsetup,
    Service_timesync,
):
    pass
