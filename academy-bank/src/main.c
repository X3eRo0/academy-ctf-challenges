#include "storage.h"
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
  Storage *storage;
  User *current_user;
  bool logged_in;
} AppContext;

static void print_banner(void) {
  printf("===============================\n");
  printf("   Welcome to Academy Bank\n");
  printf("===============================\n");
}

static void print_help(void) {
  printf("Commands:\n");
  printf("  help                       - Show this help\n");
  printf("  register <name> <paswd>    - Create a new user (100 credits)\n");
  printf("  login <name> <paswd>       - Log in as existing user\n");
  printf("  whoami                     - Show current user\n");
  printf("  balance                    - Show balance\n");
  printf("  deposit-flag <secret>      - Store a secret flag\n");
  printf("  my-flags                   - List your flags\n");
  printf("  list-flag <fid> <price> <note> - Create a listing for a flag\n");
  printf("  my-listings                - List your listings\n");
  printf("  view-listing <id>          - View listing by id\n");
  printf("  buy <listing_id>           - Buy a listing\n");
  printf("  delete-user                - Delete current user\n");
  printf("  delete-flag <id>           - Delete a flag by id\n");
  printf("  delete-listing <id>        - Delete a listing by id\n");
  printf("  logout                     - Logout\n");
  printf("  exit                       - Exit\n");
}

static void oom(void) {
  printf("error: OOM\n");
  exit(1);
}

static void require_login(AppContext *app) {
  if (!app->logged_in) {
    printf("[!] You must be logged in.\n");
  }
}

// --- Command helpers and handlers ---

static int print_flag_cb(const Flag *flag, void *ctx) {
  (void)ctx;
  printf("  id=%llu secret=%s\n", (unsigned long long)flag->id, flag->secret);
  return 0;
}

static int print_listing_cb(const Listing *l, void *ctx) {
  (void)ctx;
  printf("  id=%llu fid=%llu price=%llu sales=%llu note=%s\n",
         (unsigned long long)l->id, (unsigned long long)l->fid,
         (unsigned long long)l->price, (unsigned long long)l->sale_count,
         l->note);
  return 0;
}

static void cmd_register(AppContext *app, const char *args) {
  User *new_user = malloc(sizeof(User));
  if (!new_user)
    oom();

  while (*args == ' ')
    args++;
  if (sscanf(args, "%63s %255s", new_user->name, new_user->password) < 2) {
    printf("usage: register <name> <password>\n");
    free(new_user);
    return;
  }
  new_user->balance = 100;

  StorageResult r = storage_user_insert(app->storage, new_user, new_user);
  if (r == STORAGE_OK) {
    printf("Registered user %s with uid=%llu and balance=%llu\n",
           new_user->name, (unsigned long long)new_user->uid,
           (unsigned long long)new_user->balance);
  } else if (r == STORAGE_CONFLICT) {
    printf("[!] Username already exists\n");
  } else {
    printf("[!] Failed to register\n");
  }
  free(new_user);
}

static void cmd_login(AppContext *app, const char *args) {
  User *user = malloc(sizeof(User));
  char password[256];

  if (!user)
    oom();

  if (app->current_user) {
    printf("[!] Logout first\n");
    return;
  }

  if (!user) {
    printf("error: oom\n");
    return;
  }

  while (*args == ' ')
    args++;
  if (sscanf(args, "%63s %255s", user->name, password) < 2) {
    printf("usage: login <name> <password>\n");
    goto cleanup;
  }

  if (storage_user_get_by_name(app->storage, user->name, user) != STORAGE_OK) {
    printf("[!] Login failed\n");
    goto cleanup;
  }
  if (strncmp(password, user->password, sizeof(password)) != 0) {
    printf("[!] Invalid credentials\n");
    goto cleanup;
  }
  app->current_user = user;
  app->logged_in = true;
  printf("Logged in as %s (uid=%llu)\n", user->name,
         (unsigned long long)user->uid);
  return;

cleanup:
  free(user);
  return;
}

static void cmd_whoami(AppContext *app) {
  if (app->logged_in) {
    printf("%s uid=%llu balance=%llu\n", app->current_user->name,
           (unsigned long long)app->current_user->uid,
           (unsigned long long)app->current_user->balance);
  } else {
    printf("Not logged in\n");
  }
}

static void cmd_balance(AppContext *app) {
  if (!app->logged_in) {
    require_login(app);
    return;
  }
  if (storage_user_get_by_id(app->storage, app->current_user->uid,
                             app->current_user) == STORAGE_OK) {
    printf("Balance: %llu\n", (unsigned long long)app->current_user->balance);
  }
}

static void cmd_deposit_flag(AppContext *app, const char *args) {
  if (!app->logged_in) {
    require_login(app);
    return;
  }
  while (*args == ' ')
    args++;
  if (*args == '\0') {
    printf("usage: deposit-flag <secret>\n");
    return;
  }

  Flag *flag = malloc(sizeof(Flag));
  if (!flag)
    oom();

  flag->uid = app->current_user->uid;
  strncpy(flag->secret, args, sizeof(flag->secret) - 1);

  if (storage_flag_insert(app->storage, flag, flag) == STORAGE_OK) {
    printf("Stored flag id=%llu\n", (unsigned long long)flag->id);
  } else {
    printf("[!] Failed to store flag\n");
  }

  free(flag);
}

static void cmd_my_flags(AppContext *app) {
  if (!app->logged_in) {
    require_login(app);
    return;
  }
  printf("Your flags:\n");
  storage_iter_flags_for_user(app->storage, app->current_user->uid,
                              print_flag_cb, NULL);
}

static void cmd_list_flag(AppContext *app, const char *args) {
  if (!app->logged_in) {
    require_login(app);
    return;
  }

  Listing *listing = malloc(sizeof(Listing));
  Flag *flag = malloc(sizeof(Flag));
  if (!listing || !flag)
    oom();

  if (sscanf(args, "%llu %llu %255[^\n]", (unsigned long long *)&listing->fid,
             (unsigned long long *)&listing->price, listing->note) < 3) {
    printf("usage: list-flag <fid> <price> <note>\n");
    goto cleanup;
  }

  if (storage_flag_get_by_id(app->storage, listing->fid, flag) != STORAGE_OK ||
      flag->uid != app->current_user->uid) {
    printf("Invalid flag id\n");
    goto cleanup;
  }

  if (storage_listing_insert(app->storage, listing, listing) == STORAGE_OK) {
    printf("Created listing id=%llu price=%llu\n",
           (unsigned long long)listing->id, (unsigned long long)listing->price);
  } else {
    printf("[!] Failed to create listing\n");
  }

cleanup:
  free(listing);
  free(flag);
  return;
}

static void cmd_my_listings(AppContext *app) {
  if (!app->logged_in) {
    require_login(app);
    return;
  }
  printf("Your listings:\n");
  storage_iter_listings_for_user(app->storage, app->current_user->uid,
                                 print_listing_cb, NULL);
}

static void cmd_view_listing(AppContext *app, const char *args) {
  Listing *listing = malloc(sizeof(Listing));
  if (!listing)
    oom();

  sscanf(args, "%llu", (unsigned long long *)&listing->id);
  if (storage_listing_get_by_id(app->storage, listing->id, listing) ==
      STORAGE_OK) {
    printf("Listing id=%llu fid=%llu price=%llu sales=%llu note=%s\n",
           (unsigned long long)listing->id, (unsigned long long)listing->fid,
           (unsigned long long)listing->price,
           (unsigned long long)listing->sale_count, listing->note);
  } else {
    printf("[!] Listing not found\n");
  }

  free(listing);
}

static void cmd_buy(AppContext *app, const char *args) {
  char out[0x80];

  if (!app->logged_in) {
    require_login(app);
    return;
  }

  Listing *listing = malloc(sizeof(Listing));
  Flag *flag = malloc(sizeof(Flag));
  User *seller = malloc(sizeof(User));

  if (!listing || !flag || !seller)
    oom();

  sscanf(args, "%llu", (unsigned long long *)&listing->id);

  if (storage_listing_get_by_id(app->storage, listing->id, listing) !=
      STORAGE_OK) {
    printf("[!] Listing not found\n");
    goto cleanup;
  }

  if (storage_flag_get_by_id(app->storage, listing->fid, flag) != STORAGE_OK) {
    printf("[!] Original flag not found\n");
    goto cleanup;
  }

  if (storage_user_get_by_id(app->storage, app->current_user->uid,
                             app->current_user) != STORAGE_OK) {
    printf("[!] User not found\n");
    goto cleanup;
  }

  if (storage_user_get_by_id(app->storage, flag->uid, seller) != STORAGE_OK) {
    printf("[!] Corrupted listing\n");
    goto cleanup;
  }

  seller->balance -= listing->price * 0.05;
  if (app->current_user->balance < listing->price) {
    printf("[!] Insufficient funds\n");
    goto cleanup;
  }

  app->current_user->balance -= listing->price;
  seller->balance += listing->price;

  if (storage_user_update(app->storage, app->current_user) != STORAGE_OK) {
    printf("[!] Failed to update balance\n");
    goto cleanup;
  }

  if (storage_user_update(app->storage, seller) != STORAGE_OK) {
    printf("[!] Failed to update balance for seller\n");
    goto cleanup;
  }

  flag->uid = app->current_user->uid;
  if (storage_flag_insert(app->storage, flag, flag) != STORAGE_OK) {
    printf("[!] Failed to deliver flag\n");
    goto cleanup;
  }

  listing->sale_count += 1;
  if (storage_listing_update(app->storage, listing) != STORAGE_OK) {
    printf("[!] Failed to update listing\n");
    goto cleanup;
  }

  sprintf(out, "Purchased listing. New flag id=%lu secret=%s\n", flag->id,
          flag->secret);
  printf(out);

cleanup:
  free(listing);
  free(flag);
  free(seller);
}

static void cmd_delete_user(AppContext *app) {
  if (!app->logged_in) {
    require_login(app);
    return;
  }

  // Check no flags and no listings
  bool has_flags = false;
  int cb_flag(const Flag *f, void *ctx) {
    (void)ctx;
    has_flags = true;
    return 1;
  }
  storage_iter_flags_for_user(app->storage, app->current_user->uid, cb_flag,
                              NULL);
  bool has_listings = false;
  int cb_list(const Listing *l, void *ctx) {
    (void)ctx;
    has_listings = true;
    return 1;
  }
  storage_iter_listings_for_user(app->storage, app->current_user->uid, cb_list,
                                 NULL);
  if (has_flags || has_listings) {
    printf("[!] Cannot delete user with existing flags or listings\n");
    return;
  }
  StorageResult r =
      storage_user_delete_by_id(app->storage, app->current_user->uid);
  if (r == STORAGE_OK) {
    printf("Deleted user %llu\n", (unsigned long long)app->current_user->uid);
    app->logged_in = false;
    free(app->current_user);
    app->current_user = NULL;
  } else if (r == STORAGE_NOT_FOUND) {
    printf("[!] User not found\n");
  } else {
    printf("[!] Delete failed\n");
  }
}

static void cmd_delete_flag(AppContext *app, const char *args) {
  Flag *flag = malloc(sizeof(Flag));
  if (!flag)
    oom();

  if (!app->logged_in) {
    require_login(app);
    return;
  }

  sscanf(args, "%llu", (unsigned long long *)&flag->id);

  if (storage_flag_get_by_id(app->storage, flag->id, flag) != STORAGE_OK ||
      flag->uid != app->current_user->uid) {
    printf("[!] Flag not owned by you\n");
    goto cleanup;
  }
  // Ensure no listing uses this flag
  bool used = false;
  int cb(const Listing *l, void *ctx) {
    (void)ctx;
    if (l->fid == flag->id) {
      used = true;
      return 1;
    }
    return 0;
  }
  storage_iter_listings_for_user(app->storage, app->current_user->uid, cb,
                                 NULL);
  if (used) {
    printf("[!] Cannot delete flag used by a listing\n");
    goto cleanup;
  }
  StorageResult r = storage_flag_delete_by_id(app->storage, flag->id);
  if (r == STORAGE_OK) {
    printf("Deleted flag %llu\n", (unsigned long long)flag->id);
  } else if (r == STORAGE_NOT_FOUND) {
    printf("[!] Flag not found\n");
  } else {
    printf("[!] Delete failed\n");
  }
cleanup:
  free(flag);
  return;
}

static void cmd_delete_listing(AppContext *app, const char *args) {
  if (!app->logged_in) {
    require_login(app);
    return;
  }
  uint64_t id = 0;
  sscanf(args, "%llu", (unsigned long long *)&id);
  // Ensure listing belongs to current user (via the flag's owner)
  Listing l;
  if (storage_listing_get_by_id(app->storage, id, &l) != STORAGE_OK) {
    printf("[!] Listing not found\n");
    return;
  }
  Flag f;
  if (storage_flag_get_by_id(app->storage, l.fid, &f) != STORAGE_OK ||
      f.uid != app->current_user->uid) {
    printf("[!] Listing not owned by you\n");
    return;
  }
  StorageResult r = storage_listing_delete_by_id(app->storage, id);
  if (r == STORAGE_OK) {
    printf("Deleted listing %llu\n", (unsigned long long)id);
  } else if (r == STORAGE_NOT_FOUND) {
    printf("[!] Listing not found\n");
  } else {
    printf("[!] Delete failed\n");
  }
}

static void cmd_logout(AppContext *app) {
  if (!app->logged_in) {
    printf("[!] Login first\n");
    return;
  }

  app->logged_in = false;
  free(app->current_user);
  app->current_user = NULL;
  printf("Logged out\n");
}

int main(int argc, char **argv) {
  setbuf(stdin, NULL);
  setbuf(stdout, NULL);

  const char *db_path = argc > 1 ? argv[1] : "academy_bank.db";
  AppContext app = {0};
  if (storage_open(db_path, &app.storage) != STORAGE_OK) {
    fprintf(stderr, "Failed to open storage at %s\n", db_path);
    return 1;
  }

  print_banner();
  print_help();

  char line[1024];
  while (1) {
    printf("\n> ");
    fflush(stdout);
    if (!fgets(line, sizeof(line), stdin))
      break;
    // trim newline
    size_t len = strlen(line);
    if (len > 0 && (line[len - 1] == '\n' || line[len - 1] == '\r'))
      line[len - 1] = '\0';

    if (strncmp(line, "help", 4) == 0) {
      print_help();
      continue;
    }
    if (strncmp(line, "exit", 4) == 0) {
      break;
    }
    if (strncmp(line, "register ", 9) == 0) {
      cmd_register(&app, line + 9);
      continue;
    }
    if (strncmp(line, "login ", 6) == 0) {
      cmd_login(&app, line + 6);
      continue;
    }
    if (strncmp(line, "whoami", 6) == 0) {
      cmd_whoami(&app);
      continue;
    }
    if (strncmp(line, "balance", 7) == 0) {
      cmd_balance(&app);
      continue;
    }
    if (strncmp(line, "deposit-flag ", 13) == 0) {
      cmd_deposit_flag(&app, line + 13);
      continue;
    }
    if (strncmp(line, "my-flags", 8) == 0) {
      cmd_my_flags(&app);
      continue;
    }
    if (strncmp(line, "list-flag ", 10) == 0) {
      cmd_list_flag(&app, line + 10);
      continue;
    }
    if (strncmp(line, "my-listings", 11) == 0) {
      cmd_my_listings(&app);
      continue;
    }
    if (strncmp(line, "view-listing ", 13) == 0) {
      cmd_view_listing(&app, line + 13);
      continue;
    }
    if (strncmp(line, "buy ", 4) == 0) {
      cmd_buy(&app, line + 4);
      continue;
    }
    if (strncmp(line, "delete-user", 11) == 0) {
      cmd_delete_user(&app);
      continue;
    }
    if (strncmp(line, "delete-flag ", 12) == 0) {
      cmd_delete_flag(&app, line + 12);
      continue;
    }
    if (strncmp(line, "delete-listing ", 15) == 0) {
      cmd_delete_listing(&app, line + 15);
      continue;
    }
    if (strncmp(line, "logout", 6) == 0) {
      cmd_logout(&app);
      continue;
    }

    printf("Unknown command. Type 'help' for list of commands.\n");
  }

  storage_close(app.storage);
  return 0;
}
