const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function normalizeEmail(email) {
  return email.trim().toLowerCase();
}

export function validateLoginForm(values) {
  const errors = {};
  const email = normalizeEmail(values.email);

  if (!email) {
    errors.email = "Enter your email address.";
  } else if (!EMAIL_PATTERN.test(email)) {
    errors.email = "Use a valid email address.";
  }

  if (!values.password) {
    errors.password = "Enter your password.";
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
      email,
      password: values.password,
      rememberMe: values.rememberMe,
    },
  };
}
