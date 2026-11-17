/* SPDX-License-Identifier: GPL-3.0-or-later
 *
 * fault_injection shim: fail selected libc calls at a chosen call index.
 *
 * Build:
 *   gcc -shared -fPIC -O2 -o fi_shim.so shim.c -ldl
 *
 * Configure with environment variables (all optional, 1-based call index):
 *   FI_FAIL_MALLOC, FI_FAIL_CALLOC, FI_FAIL_REALLOC, FI_FAIL_STRDUP
 *   FI_FAIL_FORK, FI_FAIL_FOPEN, FI_FAIL_OPEN, FI_FAIL_FWRITE
 *   FI_FAIL_PIPE, FI_FAIL_WAITPID, FI_FAIL_OPEN64, FI_FAIL_FOPEN64
 * Setting a var to 0 (or leaving it unset) disables that fault.
 *
 * Each process (including fork()ed children) keeps its own counters.
 * Every injected failure is logged to stderr as "[FI] <fn> call #<n> ...".
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/wait.h>

/* glibc exports the allocator family and fork directly; dlsym(RTLD_NEXT)
 * for everything else (dlsym-induced allocations are confined to those
 * wrappers and do not disturb the malloc/calloc/realloc counters). */
extern void *__libc_malloc(size_t);
extern void *__libc_calloc(size_t, size_t);
extern void *__libc_realloc(void *, size_t);
extern pid_t __libc_fork(void);

static void *r_strdup, *r_pipe, *r_pipe2, *r_waitpid;
static void *r_fopen, *r_fopen64, *r_open, *r_open64, *r_fwrite;
#define DLSYM(name) do { if (!r_##name) r_##name = dlsym(RTLD_NEXT, #name); } while (0)

/* --- counters, one per intercepted call type --- */
static int c_malloc, c_calloc, c_realloc, c_strdup;
static int c_fork, c_fopen, c_fopen64, c_open, c_open64;
static int c_fwrite, c_pipe, c_pipe2, c_waitpid;

static int envn(const char *name)
{
	const char *s = getenv(name);
	if (!s)
		return 0;
	char *e;
	long v = strtol(s, &e, 10);
	if (e == s || v < 0)
		return 0;
	return (int)v;
}

/* Build "[FI] <fn> call #<n> -> INJECTED FAILURE\n" on the stack and write. */
static void fi_log(const char *fn, int n, const char *how)
{
	char buf[160];
	size_t i = 0;
	const char *p;
#define PUTS(s) do { for (p = (s); *p && i < sizeof buf - 1; ) buf[i++] = *p++; } while (0)
	PUTS("[FI] ");
	PUTS(fn);
	PUTS(" call #");
	char num[24];
	int k = 0, neg = 0;
	unsigned int x;
	if (n < 0) { neg = 1; x = (unsigned int)(-n); } else x = (unsigned int)n;
	do { num[k++] = (char)('0' + x % 10); x /= 10; } while (x);
	if (neg) num[k++] = '-';
	while (k) buf[i++] = num[--k];
	PUTS(" -> ");
	PUTS(how);
	PUTS("\n");
#undef PUTS
	buf[i] = 0;
	(void)!write(2, buf, i);
}

static int decision(const char *fn, int n, int failn, const char *how)
{
	if (failn && n == failn) {
		fi_log(fn, n, how);
		return 1;
	}
	return 0;
}

/* At exit, dump final per-call counts when FI_DUMP=1 (calibration aid). */
__attribute__((destructor)) static void fi_dump(void)
{
	if (!envn("FI_DUMP"))
		return;
	fi_log("TOTAL malloc", c_malloc, "");
	fi_log("TOTAL calloc", c_calloc, "");
	fi_log("TOTAL realloc", c_realloc, "");
	fi_log("TOTAL strdup", c_strdup, "");
	fi_log("TOTAL fork", c_fork, "");
	fi_log("TOTAL fopen", c_fopen, "");
	fi_log("TOTAL fopen64", c_fopen64, "");
	fi_log("TOTAL open", c_open, "");
	fi_log("TOTAL open64", c_open64, "");
	fi_log("TOTAL fwrite", c_fwrite, "");
	fi_log("TOTAL pipe", c_pipe, "");
	fi_log("TOTAL pipe2", c_pipe2, "");
	fi_log("TOTAL waitpid", c_waitpid, "");
}

/* ---------------- allocations ---------------- */
void *malloc(size_t n)
{
	int c = ++c_malloc;
	if (decision("malloc", c, envn("FI_FAIL_MALLOC"), "NULL (ENOMEM)")) {
		errno = ENOMEM;
		return NULL;
	}
	return __libc_malloc(n);
}
void *calloc(size_t n, size_t s)
{
	int c = ++c_calloc;
	if (decision("calloc", c, envn("FI_FAIL_CALLOC"), "NULL (ENOMEM)")) {
		errno = ENOMEM;
		return NULL;
	}
	return __libc_calloc(n, s);
}
void *realloc(void *p, size_t n)
{
	int c = ++c_realloc;
	if (decision("realloc", c, envn("FI_FAIL_REALLOC"), "NULL (ENOMEM)")) {
		errno = ENOMEM;
		return NULL;
	}
	return __libc_realloc(p, n);
}
char *strdup(const char *s)
{
	int c = ++c_strdup;
	if (decision("strdup", c, envn("FI_FAIL_STRDUP"), "NULL (ENOMEM)")) {
		errno = ENOMEM;
		return NULL;
	}
	DLSYM(strdup);
	return ((char *(*)(const char *))r_strdup)(s);
}

/* ---------------- process / IPC ---------------- */
pid_t fork(void)
{
	int c = ++c_fork;
	if (decision("fork", c, envn("FI_FAIL_FORK"), "-1 (EAGAIN)")) {
		errno = EAGAIN;
		return -1;
	}
	return __libc_fork();
}
int pipe(int f[2])
{
	int c = ++c_pipe;
	if (decision("pipe", c, envn("FI_FAIL_PIPE"), "-1 (EMFILE)")) {
		errno = EMFILE;
		return -1;
	}
	DLSYM(pipe);
	return ((int (*)(int *))r_pipe)(f);
}
int pipe2(int f[2], int flags)
{
	int c = ++c_pipe2;
	if (decision("pipe2", c, envn("FI_FAIL_PIPE2"), "-1 (EMFILE)")) {
		errno = EMFILE;
		return -1;
	}
	DLSYM(pipe2);
	return ((int (*)(int *, int))r_pipe2)(f, flags);
}
pid_t waitpid(pid_t p, int *st, int opt)
{
	int c = ++c_waitpid;
	if (decision("waitpid", c, envn("FI_FAIL_WAITPID"), "-1 (ECHILD)")) {
		errno = ECHILD;
		return -1;
	}
	DLSYM(waitpid);
	return ((pid_t (*)(pid_t, int *, int))r_waitpid)(p, st, opt);
}

/* ---------------- file writes ---------------- */
FILE *fopen(const char *p, const char *m)
{
	int c = ++c_fopen;
	if (decision("fopen", c, envn("FI_FAIL_FOPEN"), "NULL (EACCES)")) {
		errno = EACCES;
		return NULL;
	}
	DLSYM(fopen);
	return ((FILE *(*)(const char *, const char *))r_fopen)(p, m);
}
FILE *fopen64(const char *p, const char *m)
{
	int c = ++c_fopen64;
	if (decision("fopen64", c, envn("FI_FAIL_FOPEN64"), "NULL (EACCES)")) {
		errno = EACCES;
		return NULL;
	}
	DLSYM(fopen64);
	return ((FILE *(*)(const char *, const char *))r_fopen64)(p, m);
}
int open(const char *p, int flags, ...)
{
	mode_t mode = 0;
	va_list ap;
	va_start(ap, flags);
	if (flags & (O_CREAT | O_TMPFILE))
		mode = va_arg(ap, mode_t);
	va_end(ap);
	int c = ++c_open;
	if (decision("open", c, envn("FI_FAIL_OPEN"), "-1 (EACCES)")) {
		errno = EACCES;
		return -1;
	}
	DLSYM(open);
	return ((int (*)(const char *, int, ...))r_open)(p, flags, mode);
}
int open64(const char *p, int flags, ...)
{
	mode_t mode = 0;
	va_list ap;
	va_start(ap, flags);
	if (flags & (O_CREAT | O_TMPFILE))
		mode = va_arg(ap, mode_t);
	va_end(ap);
	int c = ++c_open64;
	if (decision("open64", c, envn("FI_FAIL_OPEN64"), "-1 (EACCES)")) {
		errno = EACCES;
		return -1;
	}
	DLSYM(open64);
	return ((int (*)(const char *, int, ...))r_open64)(p, flags, mode);
}
size_t fwrite(const void *p, size_t sz, size_t n, FILE *f)
{
	int c = ++c_fwrite;
	if (decision("fwrite", c, envn("FI_FAIL_FWRITE"), "0 (EIO)")) {
		errno = EIO;
		return 0;
	}
	DLSYM(fwrite);
	return ((size_t (*)(const void *, size_t, size_t, FILE *))r_fwrite)(p, sz, n, f);
}
