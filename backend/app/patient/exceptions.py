class PatientError(Exception):
    pass


class PatientNotFoundError(PatientError):
    pass


class PatientCodeAlreadyExistsError(PatientError):
    pass


class InvalidPatientValueError(PatientError):
    pass
