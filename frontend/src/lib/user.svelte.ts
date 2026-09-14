import { client, UsersService } from "$lib/client/sdk.gen";
import { AuthService } from "$lib/client/sdk.gen";
import type { AuthenticatedUser, UserPrivate } from "./client";
import { resetProjectState } from "$lib/project-state.svelte";
import { env } from "$env/dynamic/public";

export const defaultUser: UserPrivate = {
  id: "",
  display_name: "",
  email: "",
  first_name: "",
  last_name: "",
  phone: "",
  vote_ids: [],
  has_ysws_pii: false,
  is_superadmin: false,
  is_admin: false,
  judge_event_ids: [],
  admin_permissions: [],
};

export const defaultAuthenticatedUser: AuthenticatedUser = {
  access_token: "",
  token_type: "",
  user: defaultUser,
};

let user: AuthenticatedUser = $state(defaultAuthenticatedUser);
export function getAuthenticatedUser(): AuthenticatedUser {
  return user;
}
export function setAuthenticatedUser(newUser: AuthenticatedUser) {
  user = newUser;
}

/**
 * Browser sessions authenticate with an HttpOnly cookie, which JS can't read —
 * those users have no access_token, so identity is the only reliable signal.
 */
export function isAuthenticated(): boolean {
  return Boolean(user.user.id);
}

/** Auth headers for hand-rolled fetches; pair with `credentials: "include"`. */
export function authHeaders(): Record<string, string> {
  return user.access_token
    ? { Authorization: `Bearer ${user.access_token}` }
    : {};
}

export function signOut() {
  user = defaultAuthenticatedUser;
  void fetch(`${env.PUBLIC_API_URL}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
  resetProjectState();
  client.setConfig({
    headers: {
      Authorization: "",
    },
  });
  console.debug(
    "User signed out and cleared auth cookie request",
  );
}

export function validateToken(token?: string): Promise<void> {
  return UsersService.getCurrentUserInfoUsersCurrentGet({
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    throwOnError: false,
  })
    .then((response) => {
      if (response.error || !response.data) {
        console.error("Invalid token", response);
        throw new Error("Invalid token");
      }
      user = {
        access_token: token ?? "",
        token_type: "Bearer",
        user: response.data,
      };
      client.setConfig({
        headers: {
          Authorization: token ? `Bearer ${token}` : "",
        },
      });
      console.debug("Token verified, set user state and headers");
    })
    .catch((err) => {
      console.log("Token is invalid", err);
      signOut();
    });
}
