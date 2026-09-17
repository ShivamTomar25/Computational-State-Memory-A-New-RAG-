class PatientInformationError(Exception):
    pass


class PatientInformationNotFoundError(PatientInformationError):
    pass


class EncounterPatientMismatchError(PatientInformationError):
    pass


class InvalidClinicalValueError(PatientInformationError):
    pass


class InvalidClinicalDateRangeError(PatientInformationError):
    pass


class InvalidObservationValueError(PatientInformationError):
    pass


class FinalClinicalNoteImmutableError(PatientInformationError):
    pass


class ClinicalRecordConflictError(PatientInformationError):
    pass
