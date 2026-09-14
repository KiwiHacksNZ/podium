<script lang="ts">
  import "../app.css";
  import { Toaster } from "svelte-sonner";
  import { navigating, page } from "$app/state";
  let { children } = $props();
  import { onMount, onDestroy } from "svelte";
  import ThemeSwitcher from "$lib/components/ThemeSwitcher.svelte";
  import LoadingSpinner from "$lib/components/LoadingSpinner.svelte";
  import { applyStoredTheme, returnLoadingText } from "$lib/misc";
  import { env } from "$env/dynamic/public";
  import MaintenanceMode from "$lib/components/MaintenanceMode.svelte";

  import { getAuthenticatedUser, isAuthenticated, signOut } from "$lib/user.svelte";
  import NoticeAndHelp from "$lib/components/NoticeAndHelp.svelte";
  import UpdateUser from "$lib/components/UpdateUser.svelte";
  import AirtableHitsCounter from "$lib/components/AirtableHitsCounter.svelte";
  import DevModeIndicator from "$lib/components/DevModeIndicator.svelte";
  import { resetAirtableHits } from "$lib/airtable-hits.svelte";

  let loadingText = $state(returnLoadingText());
  let loadingTextInterval: NodeJS.Timeout = $state() as NodeJS.Timeout;
  let settingsPopoutOpen = $state(false);
  let sidebarSettingsEl: HTMLDivElement | null = $state(null);

  // Reactive variables for meta tags to ensure they update properly
  const title = $derived(
    page.data.title ? `${page.data.title} | Podium` : "Podium",
  );
  const description = $derived(
    page.data.meta?.find((m: { name: string }) => m.name === "description")
      ?.content ||
      "Podium - Kiwihacks peer-judging platform for hackathons",
  );
  const additionalMeta = $derived(
    page.data.meta?.filter((m: { name: string }) => m.name !== "description") ||
      [],
  );

  const isAuthed = $derived(isAuthenticated());

  const getDisplayName = () => {
    const user = getAuthenticatedUser().user;
    return (
      user.display_name || `${user.first_name} ${user.last_name?.[0] || ""}`
    ).trim();
  };
  const getGreetingName = () => {
    const user = getAuthenticatedUser().user;
    return user.first_name?.trim() || getDisplayName();
  };
  const toggleSettingsPopout = () => {
    settingsPopoutOpen = !settingsPopoutOpen;
  };
  const closeSettingsPopout = () => {
    settingsPopoutOpen = false;
  };
  const handleSettingsOutsideClick = (event: MouseEvent) => {
    if (!settingsPopoutOpen || !sidebarSettingsEl) return;
    const target = event.target as Node | null;
    if (target && !sidebarSettingsEl.contains(target)) {
      closeSettingsPopout();
    }
  };
  const handleSettingsEscape = (event: KeyboardEvent) => {
    if (event.key === "Escape") {
      closeSettingsPopout();
    }
  };

  // Navigation options
  const navOptions = $derived.by(() => {
    const base = {
      "/": { label: "Home", icon: "home" },
      "/projects": { label: "Projects", icon: "projects" },
      "/events": { label: "Events", icon: "events" },
    };
    const currentUser = getAuthenticatedUser().user;
    if (currentUser.is_superadmin) {
      return {
        ...base,
        "/admin": { label: "Admin", icon: "create" },
        "/superadmin": { label: "Superadmin", icon: "create" },
      };
    }
    if (currentUser.is_admin) {
      return { ...base, "/admin": { label: "Admin", icon: "create" } };
    }
    return base;
  });

  // Reset Airtable hits counter on page navigation
  $effect(() => {
    // Track page changes by watching the pathname
    page.url.pathname;
    resetAirtableHits();
  });

  // Icon path constants
  const iconPaths = {
    home: "m3 12 2-2m0 0 7-7 7 7M5 10v10a1 1 0 0 0 1 1h3m10-11 2 2m-2-2v10a1 1 0 0 1-1 1h-3m-6 0a1 1 0 0 0 1-1v-4a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v4a1 1 0 0 0 1 1m-6 0h6",
    projects:
      "M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10",
    events:
      "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2-2v14a2 2 0 002 2z",
    create: "M12 4v16m8-8H4",
    menu: "M4 6h16M4 12h16M4 18h16",
    chevron: "M19 9l-7 7-7-7",
  };

  onMount(() => {
    console.debug("Page data:", page.data);
    applyStoredTheme();
    window.addEventListener("click", handleSettingsOutsideClick);
    window.addEventListener("keydown", handleSettingsEscape);

    // Update loading text every 4 seconds
    loadingTextInterval = setInterval(() => {
      loadingText = returnLoadingText();
    }, 4000);
  });

  onDestroy(() => {
    clearInterval(loadingTextInterval);
    window.removeEventListener("click", handleSettingsOutsideClick);
    window.removeEventListener("keydown", handleSettingsEscape);
  });
</script>

<svelte:head>
  <title>{title}</title>
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  <meta name="description" content={description} />
  {#each additionalMeta as { name, content }}
    <meta {name} {content} />
  {/each}
</svelte:head>

<!-- top-center keeps toasts clear of bottom-of-screen controls on mobile, and
     daisyUI's `toast` class is deliberately absent: it is a container style
     (position: fixed; bottom: 1rem) that pinned every toast over the page. -->
<Toaster
  position="top-center"
  toastOptions={{
    unstyled: true,
    class: "alert w-full",
    classes: {
      success: "alert-success",
      error: "alert-error",
      info: "alert-info",
      warning: "alert-warning",
      closeButton: "btn btn-sm btn-circle btn-ghost btn-error",
      cancelButton: "btn btn-sm btn-circle btn-ghost btn-error",
    },
  }}
  closeButton
/>

{#if env.PUBLIC_MAINTENANCE_MODE === "true"}
  <MaintenanceMode />
{:else if page.url.pathname !== "/login" && isAuthed}
  <!-- Sidebar Layout for authenticated users -->
  <div class="drawer lg:drawer-open">
    <input id="sidebar-drawer" type="checkbox" class="drawer-toggle" />
    <div class="drawer-content flex flex-col">
      <!-- Top Navbar -->
      <div class="navbar bg-base-200 lg:hidden" id="home-navbar">
        <div class="flex-none">
          <label
            for="sidebar-drawer"
            aria-label="open sidebar"
            class="btn btn-square btn-ghost"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              class="inline-block h-6 w-6 stroke-current"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d={iconPaths.menu}
              />
            </svg>
          </label>
        </div>
        <div class="flex-1">
          <a href="/" class="flex items-center gap-2 btn btn-ghost px-2">
            <img src="/assets/kiwihacks/kiwi-text.png" alt="Podium" class="h-6 w-auto" />
          </a>
        </div>
      </div>

      <!-- Main Content -->
      <div class="flex-1 p-6">
        <!-- NoticeAndHelp - Inside main content area -->
        <NoticeAndHelp />

        {#if navigating.to && navigating.type != "form"}
          <LoadingSpinner {loadingText} />
        {:else}
          {@render children()}
        {/if}
      </div>
    </div>

    <!-- Sidebar -->
    <div class="drawer-side" id="sidebar">
      <label
        for="sidebar-drawer"
        aria-label="close sidebar"
        class="drawer-overlay"
      ></label>
      <div class="min-h-full w-80 bg-base-200 flex flex-col" id="sidebar-ui">
        <!-- Logo/Header -->
        <div class="p-6 border-b border-base-300" id="sidebar-top">
          <a href="/" class="sidebar-brand-link flex flex-col gap-1">
            <img
              src="/assets/kiwihacks/kiwi-text.png"
              alt="KiwiHacks"
              class="sidebar-brand-logo h-8 w-auto"
            />
            <p class="sidebar-brand-subtitle text-base-content/70 text-sm">
              Podium
            </p>
          </a>
        </div>

        <!-- Navigation Menu -->
        <div class="flex-1 p-4">
          <ul class="menu menu-vertical space-y-2">
            {#each Object.entries(navOptions) as [path, { label, icon }]}
              <li>
                <a
                  href={path}
                  class="flex items-center gap-3 p-3 rounded-lg transition-colors"
                  class:bg-primary={page.url.pathname === path}
                  class:text-primary-content={page.url.pathname === path}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    class="h-5 w-5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d={iconPaths[icon as keyof typeof iconPaths]}
                    />
                  </svg>
                  <span class="font-medium">{label}</span>
                </a>
              </li>
            {/each}

          </ul>
        </div>

        <!-- Bottom Section -->
        <div
          class="p-4 border-t border-base-300"
          id="sidebar-settings"
          bind:this={sidebarSettingsEl}
        >
          {#if settingsPopoutOpen}
            <div class="sidebar-settings-popout" id="settings-popout">
              <div class="sidebar-settings-section">
                <h3 class="sidebar-settings-heading">Account</h3>
                <p class="sidebar-settings-meta">
                  Signed in as: <strong>{getAuthenticatedUser().user.email}</strong>
                </p>
                <p class="sidebar-settings-meta">
                  Display Name: <strong>{getDisplayName()}</strong>
                </p>
                <div class="sidebar-settings-actions">
                  <UpdateUser
                    user={getAuthenticatedUser().user}
                    buttonClass="btn btn-outline"
                  />
                  <button class="btn btn-outline" onclick={signOut}>Sign out</button>
                </div>
              </div>
              <div class="sidebar-settings-section">
                <h3 class="sidebar-settings-heading">Theme</h3>
                <ThemeSwitcher
                  buttonClass="btn btn-outline m-0"
                  dropdownClass="dropdown-top"
                />
              </div>
            </div>
          {/if}
          <button
            class="sidebar-settings-trigger"
            aria-expanded={settingsPopoutOpen}
            aria-controls="settings-popout"
            onclick={toggleSettingsPopout}
          >
            <div class="sidebar-settings-copy">
              <p class="sidebar-settings-name">Kia ora, {getGreetingName()}!</p>
              <p class="sidebar-settings-email">{getAuthenticatedUser().user.email}</p>
            </div>
            <span class="sidebar-settings-pill" aria-hidden="true">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                class="h-5 w-5 sidebar-settings-chevron"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d={iconPaths.chevron}
                />
              </svg>
            </span>
          </button>
        </div>
      </div>
    </div>
  </div>
{:else}
  <!-- Login page or unauthenticated users without sidebar -->
  <div class="min-h-screen flex flex-col" id="landing">
    <div class="navbar bg-base-100 border-b border-base-300" id="landing-navbar">
      <div class="navbar-start"></div>
      <div class="navbar-center">
        <a href="/" class="flex items-center gap-2 btn btn-ghost px-2">
          <img src="/assets/kiwihacks/kiwi-text.png" alt="Podium" class="h-7 w-auto" />
        </a>
      </div>
      <div class="navbar-end gap-2">
        <a href="/events" class="btn btn-ghost btn-sm">Events</a>
        <a
          href="https://nova.kiwihacks.com"
          target="_blank"
          rel="noreferrer"
          class="btn btn-secondary btn-sm"
        >
          Nova
        </a>
        {#if page.url.pathname !== "/login"}
          <a href="/login" class="btn btn-primary btn-sm">Sign In</a>
        {/if}
      </div>
    </div>

    <div class="pt-6 px-6">
      <NoticeAndHelp />
    </div>

    <div class="p-6 my-auto" id="landing-content">
      {#if navigating.to && navigating.type != "form"}
        <LoadingSpinner {loadingText} />
      {:else}
        {@render children()}
      {/if}
    </div>
  </div>
{/if}

<!-- Global Theme Switcher (Bottom Left) -->
{#if !isAuthed}
  <div class="fixed bottom-4 left-4 z-50">
    <ThemeSwitcher />
  </div>
{/if}


<!-- Dev Mode Indicator (red border + notice) -->
<DevModeIndicator />
