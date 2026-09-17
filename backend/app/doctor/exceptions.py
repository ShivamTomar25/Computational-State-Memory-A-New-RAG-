class DoctorError(Exception):
    pass


class DoctorEmailAlreadyExistsError(DoctorError):
    pass


class DoctorLicenseAlreadyExistsError(DoctorError):
    pass


class DoctorNotFoundError(DoctorError):
    pass


class InvalidDoctorCredentialsError(DoctorError):
    pass


class InactiveDoctorError(DoctorError):
    pass
