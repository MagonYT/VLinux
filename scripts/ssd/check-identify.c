/* Actual Identify C under ASan/UBSan; native metadata, simulated controller. */
#include <string.h>
#include "adt.h"
#include "neo_ssd_identify.h"
#include "neo_ssd_console.h"
#include "utils.h"
#include "fixture.h"
#undef printf
extern int printf(const char *, ...);
extern void abort(void);
#define CHECK(x) do { if (!(x)) { printf("FAIL line %d: %s case=%d reads=%d writes=%d\n%s\n", __LINE__, #x, scenario, reads, writes, report); abort(); } } while (0)
#define L 0x38dcc0000ULL
#define S 0x3cdcc0000ULL
#define A 0x10020000000ULL
static u8 arena[NEO_SSD_DMA_SIZE] ALIGNED(NEO_SSD_DMA_ALIGN);
static char report[NEO_SSD_IDENTIFY_REPORT_SIZE];
static int scenario, reads, writes, delays, stages, barriers, fault_read, fault_write, after_write;
static int mismatch_read, submitted, stopped, invalidated, acked, no_completion, memory_case;
static int final_stage;
static u32 cc, csts;
static struct { u64 address; u32 value; } registers[16];
static unsigned int nr;
static char console_text[NEO_SSD_IDENTIFY_REPORT_SIZE + 128];
static size_t console_used;
static unsigned int console_cases;
void *adt;

static void console_sink(const char *text)
{
    /* Reproduce debug_printf's 512-byte buffer and literal %s formatting. */
    char buffer[512];
    CHECK(strlen(text) <= NEO_SSD_CONSOLE_CHUNK);
    snprintf(buffer, sizeof(buffer), "%s", text);
    size_t n = strlen(buffer);
    CHECK(console_used + n < sizeof(console_text));
    memcpy(console_text + console_used, buffer, n + 1);
    console_used += n;
}

static void capture_report(const char *text, size_t capacity, bool tail)
{
    memset(console_text, 0, sizeof(console_text));
    console_used = 0;
    neo_ssd_console_report(text, capacity, tail, console_sink);
    console_cases++;
}

static void check_hold_console(void)
{
    CHECK(strlen(report) > 9000);
    capture_report(report, sizeof(report), false);
    CHECK(!strcmp(console_text, report));
    capture_report(report, sizeof(report), true);
    CHECK(console_used < 1100 && strstr(console_text, "SSD_IDENTIFY_HOLD"));
    CHECK(!strcmp(console_text + console_used - NEO_SSD_CONSOLE_TAIL,
                  report + strlen(report) - NEO_SSD_CONSOLE_TAIL));
}

int adt_path_offset(const void *unused, const char *path)
{
    UNUSED(unused);
    for (unsigned int i=0; i<ARRAY_SIZE(paths); i++) if (!strcmp(path, paths[i])) return i;
    return -1;
}
const void *adt_getprop(const void *unused, int node, const char *name, u32 *length)
{
    UNUSED(unused);
    static u8 altered[512];
    for (unsigned int i=0; i<ARRAY_SIZE(props); i++) {
        if (props[i].node!=node || strcmp(props[i].name,name)) continue;
        u32 len=props[i].size;
        const void *data=props[i].data;
        if (memory_case==1 && !strcmp(name,"pre-loaded")) return NULL;
        if (memory_case==2 && !strcmp(name,"dram-base")) { static u64 bad=0x1000000000; data=&bad; }
        if (memory_case==3 && !strcmp(name,"segment-ranges")) len--;
        if (memory_case==4 && !strcmp(name,"segment-ranges")) {
            memcpy(altered,data,len); altered[16]^=4; data=altered;
        }
        if (memory_case==5 && !strcmp(name,"region-base")) { static u64 bad=A; data=&bad; }
        if (length) *length=len;
        return data;
    }
    return NULL;
}
int adt_getprop_copy(const void *tree,int node,const char *name,void *out,size_t size)
{
    u32 n;
    const void *p=adt_getprop(tree,node,name,&n);
    if (!p || n!=size) return -1;
    memcpy(out,p,size); return size;
}
static void reset(int test)
{
    scenario=test; reads=writes=delays=stages=barriers=0;
    fault_read=fault_write=mismatch_read=-1; after_write=0;
    submitted=stopped=invalidated=acked=no_completion=memory_case=final_stage=0;
    nr=0; cc=0x00474000; csts=0;
    memset(arena,0x73,sizeof(arena)); memset(report,0,sizeof(report));
}
static bool read_mock(u64 address,u32 *out)
{
    int call=reads++;
    if(call==fault_read) return false;
    *out=0;
    if(address>=0x38dc50000ULL && address<0x38dc500c0ULL) {
        u32 field=(address-0x38dc50000ULL)/0x40, index=((address-0x38dc50000ULL)%0x40)/4;
        static const u32 sart[3][16]={
            {0xea,0xff,0,0xea}, {0x3082c8,0x101ffc58,0,0x10000004}, {1,0x33,0,0x22b}
        };
        *out=sart[field][index];
        if(memory_case==6 && field==0 && index==1) *out=0xdead;
        if(memory_case==7 && field==1 && index==1) *out=A>>12;
        if(memory_case==8 && field==1 && index==0) *out=0x3082c9;
        return true;
    }
    if(address==0x300700278ULL || address==0x300700310ULL || address==0x3007003a0ULL) *out=0xff;
    else if(address==0x389600044) *out=0x10;
    else if(address==S) *out=0xf0010040;
    else if(address==S+4) *out=0x20;
    else if(address==S+8) *out=0x10100;
    else if(address==S+0x1300) *out=0xde71ce55;
    else if(address==S+0x14 || address==L+0x14) *out=cc;
    else if(address==S+0x1c || address==L+0x1c) *out=csts;
    else if(address==L+0x24908) *out=1;
    else if(address==L+0x28100) *out=63;
    else if((address>=L+0x28000 && address<=L+0x2803c) ||
            (address>=L+0x28108 && address<=L+0x28120) || address==L+0x29120 ||
            (address>=L+0x1200 && address<=L+0x1210) ||
            (address>=S+0x1200 && address<=S+0x1210) ||
            address==S+0x0c || (address>=S+0x24 && address<=S+0x34)) {}
    else CHECK(0); /* Any unexpected/doorbell read is a test failure. */
    for(unsigned int i=0;i<nr;i++) if(registers[i].address==address) *out=registers[i].value;
    if(scenario==11 && invalidated && address==L+0x28000) *out=1;
    if(call==mismatch_read) *out^=1;
    return true;
}
static bool write_mock(u64 address,u32 value)
{
    int call=writes++;
    CHECK(neo_ssd_identify_write_allowed(A,address,value));
    if(call==fault_write && !after_write) return false;
    if(address==S+0x14) {
        if(value==0x00470001) {
            CHECK(cc==0x00474000 && !submitted && nr==9);
            cc=value; csts=scenario==1?0:scenario==9?3:1;
        } else if(value==0x00474001) {
            CHECK(submitted && invalidated && acked && cc==0x00470001);
            cc=value; csts=scenario==2?5:9;
        } else {
            CHECK(cc==0x00474001 && csts==9);
            cc=value; csts=scenario==3?9:8; stopped=csts==8;
        }
    } else if(address==L+0x2490c) {
        CHECK(!submitted && cc==0x00470001 && csts==1 && barriers==2);
        /* Independently decode every byte of the only SQ command and TCB. */
        u8 command[64]={0},tcb[128]={0};
        command[0]=6; command[40]=1; tcb[1]=1;
        u64 id=A+0xc000;
        memcpy(command+24,&id,8); memcpy(tcb+24,&id,8);
        CHECK(!memcmp(arena+0x4000,command,64)); CHECK(!memcmp(arena,tcb,128));
        for(unsigned int i=64;i<4096;i++) CHECK(!arena[0x4000+i]);
        for(unsigned int i=128;i<8192;i++) CHECK(!arena[i]);
        submitted=1;
    } else if(address==L+0x28118) {
        CHECK(submitted && !invalidated && (*(u16 *)(arena+0x800e)&1)); invalidated=1;
    } else if(address==S+0x1004) {
        CHECK(invalidated && !acked); acked=1;
    } else {
        CHECK(cc==0x00474000 && !submitted && nr<ARRAY_SIZE(registers));
        registers[nr].address=address; registers[nr++].value=value;
    }
    return call!=fault_write;
}
static void delay_mock(unsigned int us)
{
    CHECK(us==100); CHECK(++delays<=160000);
    if(!submitted || no_completion || scenario==4 || (arena[0x800e]&1)) return;
    u16 tag=scenario==5?7:0, status=scenario==6?5:1;
    memcpy(arena+0x800c,&tag,2); memcpy(arena+0x800e,&status,2);
    u16 vid=0x106b; u32 nn=1;
    memcpy(arena+0xc000,&vid,2); memcpy(arena+0xc000+516,&nn,4);
    memset(arena+0xc000+24,' ',48);
    memcpy(arena+0xc000+24,"SIMULATED APPLE SSD",19);
    memcpy(arena+0xc000+64,"TEST0001",8);
    if(scenario==7) arena[0x3000]=0;
    if(scenario==8) arena[0xc000+24]=1;
}
static void rmb(void) { CHECK(submitted); }
static void wmb(void) { barriers++; }
static void stage(unsigned int n) { stages++; final_stage=n; }
static const struct neo_ssd_admin_ops ops={read_mock,write_mock,delay_mock,rmb,wmb,stage};
static enum neo_ssd_admin_result run(void) { return neo_ssd_identify(arena,A,report,sizeof(report),&ops); }
static struct neo_ssd_memory plan(void)
{
    return (struct neo_ssd_memory){.usable_base=0x10000300000ULL,.usable_size=0x1e6ab4000,
        .arena=A,.loaded={{0x10004f0c000ULL,A+NEO_SSD_DMA_SIZE-0x10004f0c000ULL},
                          {0x10001000000ULL,0x1b000000}, {0x10000300000ULL,0x100000}}};
}
int main(void)
{
    _Static_assert(NEO_SSD_DMA_SIZE == SSD_TEST_EXPECTED_DMA_SIZE,
                   "Memory planner must read the native build configuration");
    /* IMG_0842: fixed captured caller values, independent of the planner's
     * size macro. The 1 MiB caller/64 KiB callee mismatch used to stop here. */
    reset(0);
    struct neo_ssd_memory photographed = {
        .usable_base=0x10003434000ULL, .usable_size=0x1e3978000,
        .arena=0x100245c4000ULL,
        .loaded={{0x10020284000ULL,0x4440000},
                 {0x100048057ecULL,0x1a39fcf3}, {0x10004718000ULL,0xe8000}},
    };
    CHECK(neo_ssd_identify_memory(&photographed,report,sizeof(report),read_mock) ==
          (SSD_TEST_EXPECTED_DMA_SIZE == 0x100000));
    CHECK(!writes);
    reset(0);
    photographed.loaded[0].size -= 0xf0000; /* The exact 64 KiB allocation. */
    CHECK(neo_ssd_identify_memory(&photographed,report,sizeof(report),read_mock) ==
          (SSD_TEST_EXPECTED_DMA_SIZE == 0x10000));
    CHECK(!writes);
    printf("SSD_NATIVE_LAYOUT_CHECKS_PASSED cases=2\n");
    /* A failure after a long preflight was invisible in the native 62 photo. */
    reset(0); memset(report, 'x', 9000); report[9000] = '\n'; report[9001] = 0;
    fault_write = 0;
    CHECK(run() == NEO_SSD_ADMIN_HOLD && !submitted && writes == 1);
    char old_output[512];
    snprintf(old_output, sizeof(old_output), "%s", report);
    CHECK(strlen(old_output) == 511 && !strstr(old_output, "SSD_IDENTIFY_FAULT"));
    check_hold_console();
    CHECK(strstr(console_text, "SSD_IDENTIFY_FAULT write @0x3cdcc000c =0x1"));
    for (int i = 0; i < 3; i++) {
        reset(i == 2 ? 1 : 0);
        memset(report, 'x', 9000); report[9000] = '\n'; report[9001] = 0;
        if (i == 0) fault_read = 46; /* first configuration readback */
        if (i == 1) mismatch_read = 46;
        CHECK(run() == NEO_SSD_ADMIN_HOLD && !submitted);
        check_hold_console();
        CHECK(strstr(console_text, i == 0 ? "FAULT read @0x3cdcc000c" :
                    i == 1 ? "MISMATCH @0x3cdcc000c" : "TIMEOUT READY CSTS=0x0"));
    }
    const char literals[] = "%n %s %08x literal report, not a format string\n";
    capture_report(literals, sizeof(literals), false);
    CHECK(!strcmp(console_text, literals));
    capture_report("secret", 0, false); CHECK(!console_used);
    capture_report(NULL, 1, true); CHECK(!console_used);
    const char bounded[] = {'a', 'b', 'c', 'd', 'e'};
    capture_report(bounded, 3, false); CHECK(!strcmp(console_text, "abc\n"));
    capture_report(bounded, sizeof(bounded), true); CHECK(!strcmp(console_text, "abcde\n"));
    memset(report, 'z', sizeof(report)); /* no NUL at all: stay inside capacity */
    capture_report(report, sizeof(report), false);
    CHECK(console_used == sizeof(report) + 1 && console_text[sizeof(report)] == '\n');
    capture_report(report, sizeof(report), true);
    CHECK(console_used < 1100 && console_text[console_used - 1] == '\n');
    printf("SSD_CONSOLE_CHECKS_PASSED cases=%u; late write/read/mismatch/READY failures visible\n", console_cases);
    reset(0); struct neo_ssd_memory m=plan();
    CHECK(neo_ssd_identify_memory(&m,report,sizeof(report),read_mock));
    CHECK(m.count==2 && m.keep[0].start==0x10000004000ULL && m.keep[0].size==0x22c000);
    CHECK(m.keep[1].start==0x101f1a58000ULL && m.keep[1].size==0xe234000);
    CHECK(reads==48 && writes==0); printf("MEMORY_PLAN_OK actual captured ADT/SART\n%s",report);
    for(int i=0;i<48;i++) {
        reset(0); m=plan(); fault_read=i;
        CHECK(!neo_ssd_identify_memory(&m,report,sizeof(report),read_mock));
        CHECK(reads==i+1 && writes==0);
    }
    for(int i=1;i<=8;i++) {
        reset(0); m=plan(); memory_case=i;
        CHECK(!neo_ssd_identify_memory(&m,report,sizeof(report),read_mock)); CHECK(!writes);
    }
    for(int i=0;i<7;i++) {
        reset(0); m=plan();
        switch(i) {
            case 0:m.arena++;break;
            case 1:m.arena=0x10200000000ULL;break;
            case 2:m.loaded[0].start=0x10000004000ULL; m.loaded[0].size=A+NEO_SSD_DMA_SIZE-m.loaded[0].start;break;
            case 3:m.loaded[1].size=~0ULL;break;
            case 4:m.loaded[0].size--;break;
            case 5:m.loaded[1].start=A;break;
            case 6:m.usable_size=~0ULL;break;
        }
        CHECK(!neo_ssd_identify_memory(&m,report,sizeof(report),read_mock)); CHECK(!writes);
    }
    reset(0); CHECK(run()==NEO_SSD_ADMIN_STOPPED);
    CHECK(stopped && writes==15 && submitted==1 && final_stage==61);
    CHECK(strstr(report,"SSD_IDENTIFY_CONTROLLER_OK") && strstr(report,"namespace-writes=0"));
    int good_reads=reads,good_writes=writes;
    printf("IDENTIFY_SIMULATED_SUCCESS reads=%d writes=%d\n%s",reads,writes,report);
    for(int i=0;i<good_reads;i++) {
        reset(0); fault_read=i;
        enum neo_ssd_admin_result r=run();
        CHECK(r==(i<46?NEO_SSD_ADMIN_SKIPPED:NEO_SSD_ADMIN_HOLD));
        CHECK(reads==i+1 && !strstr(report,"SSD_IDENTIFY_CONTROLLER_OK"));
    }
    for(int i=0;i<good_writes;i++) for(int applied=0;applied<=1;applied++) {
        reset(0); fault_write=i; after_write=applied;
        CHECK(run()==NEO_SSD_ADMIN_HOLD); CHECK(writes==i+1);
        CHECK(!strstr(report,"SSD_IDENTIFY_CONTROLLER_OK"));
    }
    for(int i=0;i<46;i++) {
        reset(0); mismatch_read=i;
        CHECK(run()==NEO_SSD_ADMIN_SKIPPED && !writes && reads==i+1);
    }
    for(int i=46;i<56;i++) {
        reset(0); mismatch_read=i;
        CHECK(run()==NEO_SSD_ADMIN_HOLD); CHECK(reads==i+1);
    }
    for(int i=1;i<=11;i++) {
        reset(i); enum neo_ssd_admin_result r=run();
        if(i==6 || i==8 || i==10) {
            CHECK(r==NEO_SSD_ADMIN_STOPPED && stopped);
            if(i==6) CHECK(strstr(report,"SSD_IDENTIFY_COMMAND_ERROR"));
            if(i==8) CHECK(strstr(report,"SSD_IDENTIFY_DATA_INVALID"));
        } else {
            CHECK(r==NEO_SSD_ADMIN_HOLD && final_stage==62);
            CHECK(!strstr(report,"SSD_IDENTIFY_CONTROLLER_OK"));
        }
        if(i==4) CHECK(delays==10000 && writes==11 && submitted==1);
        if(i==1) CHECK(delays==50000 && writes==10 && !submitted);
    }
    reset(0); CHECK(neo_ssd_identify(arena,A,report,100,&ops)==NEO_SSD_ADMIN_SKIPPED && !writes && !reads);
    CHECK(neo_ssd_identify(arena+1,A,report,sizeof(report),&ops)==NEO_SSD_ADMIN_SKIPPED && !reads);
    CHECK(neo_ssd_identify(NULL,A,report,sizeof(report),&ops)==NEO_SSD_ADMIN_SKIPPED);
    for(u64 base=0;base<5;base++) {
        u64 banks[]={0x300700000ULL,0x389600000ULL,L,S,0x38dc50000ULL};
        for(u64 off=0;off<0x60000;off+=4) {
            u64 address=banks[base]+off;
            if(neo_ssd_identify_write_allowed(A,address,0)) CHECK(address==L+0x2490c || address==L+0x28118 || address==L+0x28108);
            CHECK(!neo_ssd_identify_write_allowed(A,address,0xdeadbeef));
            CHECK(!neo_ssd_identify_write_allowed(0,address,0));
        }
    }
    printf("ALL_IDENTIFY_HOST_CHECKS_PASSED read-faults=%d write-faults=%d memory-faults=48 preflight-mismatches=46\n",good_reads,good_writes*2);
    return 0;
}
