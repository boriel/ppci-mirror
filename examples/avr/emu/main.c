#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <simavr/sim_avr.h>
#include <simavr/sim_hex.h>
#include <simavr/sim_irq.h>
#include <simavr/avr_uart.h>
#include <simavr/sim_gdb.h>


void uart_in_hook(avr_irq_t* irq, uint32_t value, void*param)
{
  if (value == 4) {
    exit(0);
  }
  printf("uart: %X\n", value);
}

#define IRQ_UART_COUNT 1
static const char * irq_names[IRQ_UART_COUNT] = {
  [0] = "8<uart_in"
};


avr_irq_t* irq;

void init_uart(avr_t* avr)
{
  irq = avr_alloc_irq(&avr->irq_pool, 0, IRQ_UART_COUNT, irq_names);
  avr_irq_register_notify(irq + 0, uart_in_hook, 0);
  avr_irq_t* src = avr_io_getirq(avr, AVR_IOCTL_UART_GETIRQ('0'), UART_IRQ_OUTPUT);
  avr_connect_irq(src, irq + 0);
}

int main(int argc, char* argv[])
{
  avr_t* avr;
  avr = avr_make_mcu_by_name("atmega328p");
  if (!avr) {
    fprintf(stderr, "Error making core\n");
    exit(1);
  }

  uint32_t boot_size, boot_base;
  if (argc < 1) {
    fprintf(stderr, "Provide the hex file\n");
  }

  char *bootpath = argv[1]; // "test.hex";

  printf("Loading %s\n", bootpath);

  uint8_t *boot = read_ihex_file(bootpath, &boot_size, &boot_base);
  if (!boot) {
    fprintf(stderr, "Error loading %s\n", bootpath);
    exit(1);
  }

  avr_init(avr);
  avr->frequency = 16000000;
  memcpy(avr->flash + boot_base, boot, boot_size);
  avr->pc = boot_base;
  avr->codeend = avr->flashend;
  avr->log = LOG_TRACE;

  init_uart(avr);

#ifdef WITH_GDB_DEBUG_SERVER
  avr->gdb_port = 1234;
  avr->state = cpu_Stopped;
  avr_gdb_init(avr);
#endif

  int state = cpu_Running;
  while (!(state == cpu_Done || state == cpu_Crashed)) {
    state = avr_run(avr);
  }

  return 0;
}
