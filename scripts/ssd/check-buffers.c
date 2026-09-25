/* Actual firmware discovery and buffer policy; independent simulated device. */
#include <string.h>
#include "adt.h"
#include "neo_ssd_buffers.h"
#include "neo_ssd_services.h"
#include "neo_ssd_console.h"
#include "utils.h"
#include "fixture.h"
#undef printf
extern int printf(const char *, ...);
extern int fflush(void *);
extern void abort(void);
#define ASC 0x389600000ULL
#define SART 0x38dc50000ULL
#define A 0x100241c4000ULL
#define TYPE(n) ((u64)(n)<<52)
#define CHECK(x) do { if(!(x)) {printf("FAIL %d %s case=%d io=%u rx=%u grants=%u\n%s",__LINE__,#x,scenario,calls,service_rx,grants,report);fflush(NULL);abort();}}while(0)
static char report[16384], visible[1200];
static unsigned visible_used, calls, writes, write32s, grants, starts, discovery_rx, service_rx;
static unsigned checkpoint, polls, delays, prepares, acks, last_kind;
static u32 table[16][3];
static u64 held, allocated, addresses[4], lengths[4];
static int scenario, fault_at, after_write;
static bool faulted, active, discovered, pending, receiving, prepared;
void *adt;

int adt_path_offset(const void *tree,const char *path)
{
    UNUSED(tree);
    for(unsigned i=0;i<ARRAY_SIZE(paths);i++) if(!strcmp(path,paths[i])) return i;
    return -1;
}
const void *adt_getprop(const void *tree,int node,const char *name,u32 *length)
{
    UNUSED(tree);
    if(node==1 && !strcmp(name,"asc-dram-mask") && scenario==21) {
        static u64 mask=1ULL<<40;
        if(length)*length=8;return &mask;
    }
    for(unsigned i=0;i<ARRAY_SIZE(props);i++) if(props[i].node==node && !strcmp(props[i].name,name)) {
        if(length)*length=props[i].size;
        if(scenario==20 && !strcmp(name,"sart-version")) {static u32 version=4;return &version;}
        return props[i].data;
    }
    return NULL;
}
int adt_getprop_copy(const void *tree,int node,const char *name,void *out,size_t size)
{
    u32 n=0;const void *p=adt_getprop(tree,node,name,&n);
    if(!p || n!=size)return -1;memcpy(out,p,size);return size;
}
bool adt_is_compatible(const void *tree,int node,const char *expected)
{
    u32 n=0;const char *p=adt_getprop(tree,node,"compatible",&n);
    return p && n==strlen(expected)+1 && !memcmp(p,expected,n);
}
static bool touch(unsigned kind)
{
    CHECK(!faulted);last_kind=kind;unsigned n=calls++;
    if((int)n==fault_at) {faulted=true;return false;}return true;
}
static bool rd32(u64 address,u32 *out)
{
    if(!touch(0))return false;
    if(address>=SART && address<SART+0xc0 && !(address&3)) {
        unsigned field=(address-SART)/0x40,slot=((address-SART)%0x40)/4;
        *out=table[slot][field];
        if(scenario==6 && write32s==3 && slot==1 && field==0)*out^=1;
        return true;
    }
    switch(address) {
        case ASC+0x44:*out=0x10;break;
        case 0x38dcc0014:case 0x3cdcc0014:*out=0x00474000;break;
        case 0x38dcc001c:case 0x3cdcc001c:*out=0;break;
        case ASC+0x8110:*out=scenario==13 && prepared?(1U<<16):0x27701;break;
        case ASC+0x8114:
            if(!discovered)*out=active && discovery_rx<3?0x2201:0x22201;
            else {
                CHECK(starts==6);polls++;
                bool ready=service_rx<11;
                if(scenario==12)ready=service_rx<1;
                if(scenario==14)ready=false;
                if(scenario==16 || scenario==18)ready=true;
                if(scenario==17)ready=!service_rx || polls%6000==0;
                if(scenario==28)ready=service_rx<27;
                if(scenario==29 || scenario==31)ready=service_rx<43;
                if(scenario==30)ready=true;
                *out=ready?0x2201:0x22201;
            }
            break;
        default:CHECK(false);
    }
    return true;
}
static void incoming(u64 *message,unsigned *ep)
{
    static const unsigned eps[]={1,2,2,4,8,2,4,4,3,10,0};
    unsigned n=service_rx;*ep=n<11?eps[n]:10;
    switch(n) {
        case 0:*message=0x0010800000000000ULL;break;
        case 1:*message=TYPE(8)|(128ULL<<24)|16;break;
        case 2:*message=TYPE(1)|(4ULL<<44);break;
        case 3:*message=TYPE(1)|(8ULL<<44);break;
        case 4:*message=(1ULL<<56)|(0x5000ULL<<36);break;
        case 5:*message=TYPE(5)|3;break;
        case 6:*message=TYPE(8);break;
        case 7:*message=TYPE(12);break;
        case 10:*message=TYPE(7)|0x20;break;
        default:*message=TYPE(9)|n;
    }
    if(n==0 && scenario==1)*message=TYPE(1)|(1ULL<<44);
    if(n==0 && scenario==2)*ep=2;
    if(n==2 && scenario==7)*message|=0x101ffc58000ULL;
    if(n==2 && scenario==8) {*ep=1;*message=0x0010800000000000ULL;}
    if(n==2 && scenario==9)*message=TYPE(1)|(0x41ULL<<44);
    if(n==2 && scenario==10)*message=TYPE(1);
    if(n==1 && scenario==11)*ep=32;
    if(n==10 && scenario==15)*message=TYPE(7)|0x10;
    if(n && (scenario==16 || scenario==17)) {*ep=10;*message=TYPE(9)|n;}
    if(n>=5 && scenario==18) {*ep=2;*message=TYPE(5)|3;}
    if(scenario==19 && (n==2 || n==3))*message=TYPE(1)|(0x40ULL<<44);
    if(scenario==19 && n==4)*message=(1ULL<<56)|(0x40000ULL<<36);
    if(n==1 && scenario==22)*ep=257;
    if(n==6 && scenario==23)*message=TYPE(8)|1; /* unknown metadata: no ACK */
    if(n==10 && scenario==24)*message=0x1070000000000020ULL;
    /* IMG_0843: two buffers, followed by canonical endpoint-4 reports.
     * Only case 28 replays the observed 27-message prefix. Cases 29-31 are
     * independent hypothetical continuations, not claims about the device. */
    if(scenario>=28 && scenario<=31) {
        *ep=n?4:1;
        *message=!n?0x0010800000000000ULL:n==1?TYPE(1)|(4ULL<<44):TYPE(8);
        if(n==42 && (scenario==29 || scenario==31)) {*ep=0;*message=TYPE(7)|0x20;}
        if(n==2 && scenario==31)*message|=1; /* must not broaden canonical ACKs */
    }
}
static bool rd64(u64 address,u64 *out)
{
    CHECK(neo_ssd_firmware_read64_allowed(address));
    if(!touch(0))return false;
    CHECK(receiving==(address==ASC+0x8838));receiving=!receiving;
    u64 message;unsigned ep=0;
    if(!discovered) {
        CHECK(active && discovery_rx<3);
        if(!discovery_rx)message=TYPE(1)|(scenario==25?0x000b000b:0x000c000c);
        else if(discovery_rx==1)message=TYPE(8)|(scenario==26?0x11f:0x51f);
        else message=TYPE(8)|(1ULL<<51)|(1ULL<<32)|3;
    } else incoming(&message,&ep);
    *out=address==ASC+0x8830?message:0x0010560000000000ULL|ep;
    if(address==ASC+0x8838) {if(discovered)service_rx++;else discovery_rx++;}
    return true;
}
static bool wr64(u64 address,u64 value)
{
    CHECK(neo_ssd_buffers_write64_allowed(A,address,value));
    bool ok=touch(1);writes++;
    if(!ok && !after_write)return false;
    if(address==ASC+0x8800) {CHECK(!pending);pending=true;held=value;return ok;}
    CHECK(pending);pending=false;
    if(!active) {CHECK(!value && held==(TYPE(6)|0x220));active=true;}
    else if(!discovered) {
        CHECK(!value);
        if(discovery_rx==1)CHECK(held==(TYPE(2)|(scenario==25?0x000b000b:0x000c000c)));
        else if(discovery_rx==2)CHECK(held==(TYPE(8)|1));
        else {CHECK(discovery_rx==3 && held==(TYPE(8)|(1ULL<<51)|(1ULL<<32)));discovered=true;}
    } else if(!value) {
        static const unsigned eps[]={1,2,3,4,8,10};
        CHECK(starts<6 && held==(TYPE(5)|((u64)eps[starts]<<32)|2));starts++;
    } else if((held>>52)==1 || (held>>56)==1) {
        CHECK(prepared && write32s==3 && table[2][0]==0xff && grants<4);
        static const unsigned eps[]={1,2,4,8};
        bool native_stream=scenario>=28 && scenario<=31;
        CHECK(native_stream ? grants<2 && value==(grants?4:1) : value==eps[grants]);
        u64 addr=value==8?(held&0xfffffffffULL)<<12:held&0xfffffffffffULL;
        u64 size=value==8?(held>>36)&0xfffff:((held>>44)&0xff)<<12;
        u64 expected=grants==0?0x8000:scenario==19?0x40000:grants==1?0x4000:grants==2?0x8000:0x5000;
        CHECK(size==expected && addr==A+allocated && size<=0x40000);
        CHECK(addr+size<=A+NEO_SSD_BUFFER_POOL_SIZE);
        for(unsigned i=0;i<grants;i++)CHECK(addr>=addresses[i]+lengths[i]);
        addresses[grants]=addr;lengths[grants]=size;grants++;allocated+=ALIGN_UP(size,0x4000);
    } else {
        CHECK(grants==4 || (scenario>=28 && scenario<=31 && grants==2));
        CHECK((value==2 && held==(TYPE(5)|3)) || (value==4 && (held==TYPE(8) || held==TYPE(12))));acks++;
    }
    return ok;
}
static bool wr32(u64 address,u32 value)
{
    CHECK(neo_ssd_buffers_sart_write_allowed(A,address,value) && prepared && !grants);
    bool ok=touch(2);write32s++;
    if(!ok && !after_write)return false;
    CHECK(write32s<=3);
    static const unsigned offsets[]={0x48,0x88,8};CHECK(address==SART+offsets[write32s-1]);
    if(scenario!=5 || write32s!=1)table[2][(address-SART)/0x40]=value;
    return ok;
}
static bool prepare(u64 arena)
{
    CHECK(!faulted && arena==A && !prepared && !write32s && !grants);prepares++;
    if(scenario==4)return false;prepared=true;return true;
}
static void delay(unsigned us) {CHECK(!faulted && us==100);delays++;}
static void stage(unsigned n) {CHECK((n>=63 && n<=68) || (n>=72 && n<=78));checkpoint=n;}
static const struct neo_ssd_buffer_ops ops={{rd32,rd64,wr64,delay,stage},wr32,prepare};
static void reset(int s)
{
    scenario=s;fault_at=-1;after_write=0;
    calls=writes=write32s=grants=starts=discovery_rx=service_rx=checkpoint=polls=delays=prepares=acks=last_kind=0;
    faulted=active=discovered=pending=receiving=prepared=false;active=s==27;held=allocated=0;
    memset(table,0,sizeof(table));
    table[0][0]=0xea;table[0][1]=0x3082c8;table[0][2]=1;
    table[1][0]=0xff;table[1][1]=0x101ffc58;table[1][2]=0x33;
    table[3][0]=0xea;table[3][1]=0x10000004;table[3][2]=0x22b;
    if(s==3){table[2][0]=0xff;table[2][1]=0x10001000;table[2][2]=8;}
    memset(report,'x',9000);report[9000]='\n';report[9001]=0;
}
static void emit(const char *s)
{
    size_t n=strlen(s);CHECK(n<=240 && visible_used+n<sizeof(visible));
    memcpy(visible+visible_used,s,n+1);visible_used+=n;
}
static unsigned run(void)
{
    unsigned n=neo_ssd_buffers_probe(A,report,sizeof(report),&ops);
    CHECK(n==checkpoint);visible_used=0;visible[0]=0;
    neo_ssd_console_report(report,sizeof(report),true,emit);
    CHECK(strstr(visible,"SSD_BUF_HOLD") && strstr(visible,"NVMe-commands=0; retain pool"));
    for(unsigned ep=0;ep<6;ep++) {static const char *tags[]={"ep=1 ","ep=2 ","ep=3 ","ep=4 ","ep=8 ","ep=10 "};CHECK(strstr(visible,tags[ep]));}
    return n;
}
int main(void)
{
    reset(28);unsigned replay=run();
    printf("NATIVE_PREFIX_REPLAY checkpoint=%u rx=%u grants=%u acks=%u tx-words=%u\n",
           replay,service_rx,grants,acks,writes-8);
    CHECK(replay==75 && service_rx==27 && grants==2 && acks==25 && write32s==3);
    reset(0);CHECK(run()==76 && grants==4 && write32s==3 && acks==3 && prepares==1);
    unsigned positions=calls,write_fault_cases=0;
    printf("BUFFER_SIMULATED_BOOT io=%u\n%s",positions,visible);
    for(unsigned i=0;i<positions;i++)for(int applied=0;applied<2;applied++) {
        reset(0);fault_at=i;after_write=applied;
        CHECK(run()==78 && faulted && calls==i+1);
        if(last_kind)write_fault_cases++;
    }
    for(int s=1;s<=31;s++) {
        reset(s);unsigned n=run();
        unsigned expected=s==12 || s==15 || s==16 || s==17 || s==18 || s==28 || s==30?75:
                          s==19 || s==23 || s==27 || s==29 || s==31?76:78;
        CHECK(n==expected);
        if(s==3 || s==4)CHECK(!write32s && !grants);
        if(s==5)CHECK(write32s==1 && !grants);
        if(s==6)CHECK(write32s==3 && !grants);
        if(s==12)CHECK(grants==1 && polls==10001);
        if(s==13)CHECK(grants==0 && delays==2000);
        if(s==14)CHECK(!prepares && !write32s && polls==10000);
        if(s==16)CHECK(service_rx==256 && grants==1);
        if(s==17)CHECK(polls==50000 && grants==1);
        if(s==18)CHECK(service_rx==256 && writes<=532 && strstr(report,"end=message-limit"));
        if(s==19)CHECK(allocated==0xc8000 && grants==4);
        if(s==20 || s==21)CHECK(!calls);
        if(s==23)CHECK(acks==2);
        if(s==25 || s==26)CHECK(!starts && !write32s);
        if(s==28)CHECK(service_rx==27 && grants==2 && acks==25 && polls==10027);
        if(s==29)CHECK(service_rx==43 && grants==2 && acks==40 && write32s==3);
        if(s==30)CHECK(service_rx==256 && grants==2 && acks==254 && writes==532 &&
                       strstr(report,"end=message-limit"));
        if(s==31)CHECK(service_rx==43 && acks==39);
    }
    reset(30);CHECK(run()==75);
    unsigned stream_positions=calls,stream_write_faults=0;
    for(unsigned i=0;i<stream_positions;i++)for(int applied=0;applied<2;applied++) {
        reset(30);fault_at=i;after_write=applied;
        CHECK(run()==78 && faulted && calls==i+1);
        if(last_kind)stream_write_faults++;
    }
    unsigned poll_faults=0;
    for(int s=12;s<=17;s++) {
        reset(s);run();unsigned total=calls;
        for(unsigned j=0;j<3;j++) {
            reset(s);fault_at=j==0?45:j==1?total/2:total-1;
            CHECK(run()==78 && faulted && calls==(unsigned)fault_at+1);poll_faults++;
        }
    }
    reset(0);CHECK(neo_ssd_buffers_probe(A,NULL,sizeof(report),&ops)==78 && !calls);
    CHECK(neo_ssd_buffers_probe(A,report,1,&ops)==78 && !calls);
    CHECK(neo_ssd_buffers_probe(A,report,sizeof(report),NULL)==78 && !calls);
    u64 invalid[]={0,A+1,0x10000000000ULL-0x4000,0x10200000000ULL-0x4000,~0ULL};
    for(unsigned i=0;i<ARRAY_SIZE(invalid);i++) {
        reset(0);CHECK(neo_ssd_buffers_probe(invalid[i],report,sizeof(report),&ops)==78 && !calls);
        CHECK(!neo_ssd_buffers_sart_write_allowed(invalid[i],SART+8,0xff));
    }
    for(u64 off=0;off<0xc000;off+=4) {
        CHECK(neo_ssd_buffers_sart_write_allowed(A,SART+off,0xff)==(off==8));
        CHECK(neo_ssd_buffers_sart_write_allowed(A,SART+off,A>>12)==(off==0x48));
        CHECK(neo_ssd_buffers_sart_write_allowed(A,SART+off,0x100)==(off==0x88));
        CHECK(!neo_ssd_buffers_sart_write_allowed(A,SART+off,0));
    }
    for(unsigned ep=0;ep<256;ep++)CHECK(neo_ssd_buffers_write64_allowed(A,ASC+0x8808,ep)==(ep==0 || ep==1 || ep==2 || ep==4 || ep==8));
    CHECK(!neo_ssd_buffers_write64_allowed(A,ASC+0x8800,TYPE(0xb)|0x20));
    CHECK(!neo_ssd_buffers_write64_allowed(A,ASC+0x8800,TYPE(1)|(8ULL<<44)|(A-0x4000)));
    CHECK(!neo_ssd_buffers_write64_allowed(A,ASC+0x8800,TYPE(1)|(8ULL<<44)|(A+NEO_SSD_BUFFER_POOL_SIZE)));
    CHECK(!neo_ssd_buffers_write64_allowed(A,ASC+0x8800,TYPE(1)|(8ULL<<44)|(A+1)));
    printf("NATIVE_STREAM_FAULT_CHECKS_PASSED positions=%u write-fault-cases=%u replay-cases=4\n",stream_positions,stream_write_faults);
    printf("ALL_BUFFER_HOST_CHECKS_PASSED mmio-positions=%u write-fault-cases=%u protocol-cases=31 poll-fault-cases=%u\n",positions,write_fault_cases,poll_faults);
    return 0;
}
