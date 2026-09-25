/* Read-only touchpad diagnostic. Does not grab devices or read keyboard events.
 * libinput ABI: https://wayland.freedesktop.org/libinput/doc/latest/api/libinput_8h_source.html */
typedef unsigned long size_t;
extern int open(const char *,int,...),close(int),ioctl(int,unsigned long,...),*__errno_location(void),printf(const char *,...),fflush(void *),usleep(unsigned int),atoi(const char *),strcmp(const char *,const char *);
extern long read(int,void *,size_t);
extern void *dlopen(const char *,int),*dlsym(void *,const char *);
extern char *dlerror(void);
extern int __libc_start_main(int (*)(int,char **),int,char **,void *,void *,void *,void *);
struct interface {int (*open)(const char *,int,void *);void (*close)(int,void *);};
struct event {long sec,usec;unsigned short type,code;int value;};
static int restricted_open(const char *p,int f,void *d){int fd=open(p,f);return fd<0?-*__errno_location():fd;}
static void restricted_close(int fd,void *d){close(fd);}
#define LOAD(ret,name,args) ret (*name)args=dlsym(lib,#name);if(!name){printf("BATCH_INPUT_MISSING_API %s\n",#name);return 3;}
int main(int argc,char **argv)
{
 int fd,seconds,slot=0,ids[32],dropping=0,maxcontacts=0; char name[256]={0};
 unsigned long frames=0,one=0,two=0,multi=0,drops=0,motions=0,scrolls=0,press=0,release=0,intervals=0,total=0,min=~0UL,max=0,last=0;
 void *lib,*ctx,*dev,*ev;struct interface iface={restricted_open,restricted_close};
 if(argc!=3||(seconds=atoi(argv[2]))<1||seconds>300)return 2;
 fd=open(argv[1],0x800);if(fd<0)return 2;
 if(ioctl(fd,0x81004506UL,name)<0||strcmp(name,"Apple Neo Trackpad")){printf("BATCH_INPUT_REFUSED_OTHER_DEVICE\n");close(fd);return 2;}
 for(int i=0;i<32;i++)ids[i]=-1;
 lib=dlopen("libinput.so.10",2);if(!lib){printf("BATCH_INPUT_LIBRARY_ERROR %s\n",dlerror());close(fd);return 2;}
 LOAD(void *,libinput_path_create_context,(const struct interface *,void *));
 LOAD(void *,libinput_path_add_device,(void *,const char *));
 LOAD(int,libinput_dispatch,(void *));LOAD(void *,libinput_get_event,(void *));LOAD(int,libinput_event_get_type,(void *));
 LOAD(void *,libinput_event_get_pointer_event,(void *));LOAD(double,libinput_event_pointer_get_dx,(void *));LOAD(double,libinput_event_pointer_get_dy,(void *));
 LOAD(int,libinput_event_pointer_has_axis,(void *,int));LOAD(double,libinput_event_pointer_get_scroll_value,(void *,int));
 LOAD(int,libinput_event_pointer_get_button_state,(void *));LOAD(void,libinput_event_destroy,(void *));LOAD(void *,libinput_unref,(void *));
 LOAD(unsigned int,libinput_device_config_scroll_get_methods,(void *));LOAD(unsigned int,libinput_device_config_scroll_get_method,(void *));
 ctx=libinput_path_create_context(&iface,0);if(!ctx)return 3;dev=libinput_path_add_device(ctx,argv[1]);if(!dev)return 3;
 printf("BATCH_INPUT_READY device=%s scroll_methods=%u active_scroll=%u seconds=%d\n",name,libinput_device_config_scroll_get_methods(dev),libinput_device_config_scroll_get_method(dev),seconds);fflush(0);
 for(int tick=0;tick<seconds*100;tick++){
  struct event b[64];long n;
  while((n=read(fd,b,sizeof(b)))>0){
   if(n%sizeof(*b)){printf("BATCH_INPUT_BAD_EVENT_SIZE\n");return 4;}
   for(int j=0;j<n/(long)sizeof(*b);j++){
    struct event *e=&b[j];
    if(e->type==0&&e->code==3){dropping=1;drops++;continue;}
    if(dropping){if(e->type==0&&e->code==0){int mt[33];mt[0]=0x39;if(ioctl(fd,0x8084450aUL,mt)<0)return 4;for(int k=0;k<32;k++)ids[k]=mt[k+1];dropping=0;}continue;}
    if(e->type==3&&e->code==0x2f)slot=e->value;
    if(e->type==3&&e->code==0x39&&slot>=0&&slot<32)ids[slot]=e->value;
    if(e->type==0&&e->code==0){int contacts=0;unsigned long now=e->sec*1000000UL+e->usec;for(int k=0;k<32;k++)contacts+=ids[k]>=0;
     frames++;one+=contacts==1;two+=contacts==2;multi+=contacts>=3;if(contacts>maxcontacts)maxcontacts=contacts;
     if(last&&now>last&&now-last<250000){unsigned long dt=now-last;intervals++;total+=dt;if(dt<min)min=dt;if(dt>max)max=dt;}last=now;
    }
   }
  }
  if(n<0&&*__errno_location()!=11&&*__errno_location()!=4)return 4;
  if(libinput_dispatch(ctx)<0)return 4;
  while((ev=libinput_get_event(ctx))){int type=libinput_event_get_type(ev);void *p;
   if(type==400){p=libinput_event_get_pointer_event(ev);if(libinput_event_pointer_get_dx(p)||libinput_event_pointer_get_dy(p))motions++;}
   if(type==405){p=libinput_event_get_pointer_event(ev);int nonzero=0;for(int a=0;a<2;a++)if(libinput_event_pointer_has_axis(p,a)&&libinput_event_pointer_get_scroll_value(p,a)!=0)nonzero=1;scrolls+=nonzero;}
   if(type==402){p=libinput_event_get_pointer_event(ev);if(libinput_event_pointer_get_button_state(p))press++;else release++;}
   libinput_event_destroy(ev);
  }
  if(tick%100==0){printf("BATCH_INPUT frames=%lu one=%lu two=%lu three_plus=%lu max_contacts=%d motion=%lu scroll=%lu clicks=%lu/%lu drops=%lu interval_us=%lu/%lu/%lu\n",frames,one,two,multi,maxcontacts,motions,scrolls,press,release,drops,intervals?min:0,intervals?total/intervals:0,max);fflush(0);}
  usleep(10000);
 }
 libinput_unref(ctx);close(fd);printf("BATCH_INPUT_DONE\n");return 0;
}
__attribute__((used)) void entry(unsigned long *sp){__libc_start_main(main,(int)sp[0],(char **)(sp+1),0,0,0,sp);}
__asm__(".global _start\n_start:\nmov x0,sp\nbl entry\nbrk #0\n");
