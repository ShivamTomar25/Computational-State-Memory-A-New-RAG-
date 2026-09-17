const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function clean(value) {
  return value.trim();
}

function nullableClean(value) {
  const cleanedValue = clean(value);

  return cleanedValue || null;
}

export function validateRegisterDoctorForm(values) {
  const errors = {};
  const fullName = clean(values.fullName);
  const email = clean(values.email).toLowerCase();
  const specialization = nullableClean(values.specialization);
  const medicalLicenseNumber = nullableClean(values.medicalLicenseNumber);
  const organizationName = nullableClean(values.organizationName);

  if (fullName.length < 2) {
    errors.fullName = "Enter the doctor's full name.";
  }

  if (!email) {
    errors.email = "Enter an email address.";
  } else if (!EMAIL_PATTERN.test(email)) {
    errors.email = "Use a valid email address.";
  }

  if (!values.password) {
    errors.password = "Enter a password.";
  } else if (values.password.length < 8) {
    errors.password = "Password must be at least 8 characters.";
  } else if (values.password.length > 128) {
    errors.password = "Password must be 128 characters or fewer.";
  }

  if (Object.keys(errors).length > 0) {
    return {
      errors,
      payload: null,
    };
  }

  return {
    errors,
    payload: {
      full_name: fullName,
      email,
      password: values.password,
      specialization,
      medical_license_number: medicalLicenseNumber,
      organization_name: organizationName,
    },
  };
}
