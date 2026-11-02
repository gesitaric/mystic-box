import {
  AuthenticationDetails,
  CognitoUser,
  CognitoUserPool,
} from "amazon-cognito-identity-js";

const USER_POOL_ID = import.meta.env.VITE_COGNITO_USER_POOL_ID;
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID;

let userPool = null;

function getUserPool() {
  if (!USER_POOL_ID || !CLIENT_ID) {
    throw new Error(
      "Sign-in is not configured. Set VITE_COGNITO_USER_POOL_ID and VITE_COGNITO_CLIENT_ID."
    );
  }

  if (!userPool) {
    userPool = new CognitoUserPool({
      UserPoolId: USER_POOL_ID,
      ClientId: CLIENT_ID,
    });
  }

  return userPool;
}

function createCognitoUser(email) {
  return new CognitoUser({
    Username: email,
    Pool: getUserPool(),
  });
}

export function signUp(email, password) {
  return new Promise((resolve, reject) => {
    getUserPool().signUp(email, password, [], null, (error, result) => {
      if (error) {
        reject(error);
        return;
      }

      resolve(result);
    });
  });
}

export function confirmSignUp(email, code) {
  const user = createCognitoUser(email);

  return new Promise((resolve, reject) => {
    user.confirmRegistration(code, true, (error, result) => {
      if (error) {
        reject(error);
        return;
      }

      resolve(result);
    });
  });
}

export function signIn(email, password) {
  const user = createCognitoUser(email);
  const authenticationDetails = new AuthenticationDetails({
    Username: email,
    Password: password,
  });

  return new Promise((resolve, reject) => {
    user.authenticateUser(authenticationDetails, {
      onSuccess: (session) => {
        resolve({ email: user.getUsername(), session });
      },
      onFailure: (error) => {
        reject(error);
      },
      newPasswordRequired: () => {
        reject(new Error("A new password must be set for this user."));
      },
    });
  });
}

export function getCurrentSession() {
  let user;

  try {
    user = getUserPool().getCurrentUser();
  } catch {
    return Promise.resolve(null);
  }

  if (!user) return Promise.resolve(null);

  return new Promise((resolve) => {
    user.getSession((error, session) => {
      if (error || !session || !session.isValid()) {
        resolve(null);
        return;
      }

      resolve({ email: user.getUsername(), session });
    });
  });
}

export function signOut() {
  try {
    const user = getUserPool().getCurrentUser();
    if (user) user.signOut();
  } catch {
    // Sem sessão/configuração: nada a fazer.
  }
}

export function describeAuthError(error) {
  const code = error?.code ?? error?.name;

  switch (code) {
    case "NotAuthorizedException":
    case "UserNotFoundException":
      return "Incorrect email or password.";
    case "UsernameExistsException":
      return "An account with this email already exists.";
    case "UserNotConfirmedException":
      return "Confirm your email before signing in.";
    case "CodeMismatchException":
      return "Invalid confirmation code.";
    case "ExpiredCodeException":
      return "Code expired. Request a new code.";
    case "InvalidPasswordException":
      return error?.message ?? "The password does not meet the requirements.";
    case "LimitExceededException":
      return "Too many attempts. Wait a moment and try again.";
    case "InvalidParameterException":
      return error?.message ?? "Invalid data.";
    default:
      return error?.message ?? "Something went wrong. Please try again.";
  }
}
