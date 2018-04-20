import unittest
import io
from ppci.common import CompilerError
from ppci.lang.c import CBuilder, CPrinter
from ppci.lang.c import CSynthesizer
from ppci.lang.c.options import COptions
from ppci.lang.c.utils import replace_escape_codes
from ppci.arch.example import ExampleArch
from ppci import ir
from ppci.irutils import Verifier


class CUtilitiesTestCase(unittest.TestCase):
    def test_escape_strings(self):
        """ Test string escape codes """
        src = r'\' \" \? \\ \a \b \f \n \r \t \v \0 \001'
        expected = '\' " ? \\ \a \b \f \n \r \t \v \0 \1'
        result = replace_escape_codes(src)
        self.assertEqual(expected, result)

    def test_escape_unicode(self):
        """ Test string escape unicodes """
        src = r'H \xfe \u1234 \U00010123'
        expected = 'H \xfe \u1234 \U00010123'
        result = replace_escape_codes(src)
        self.assertEqual(expected, result)


class CFrontendTestCase(unittest.TestCase):
    """ Test if various C-snippets build correctly """
    def setUp(self):
        arch = ExampleArch()
        self.builder = CBuilder(arch.info, COptions())

    def do(self, src):
        f = io.StringIO(src)
        try:
            ir_module = self.builder.build(f, None)
        except CompilerError as compiler_error:
            lines = src.split('\n')
            compiler_error.render(lines)
            raise
        assert isinstance(ir_module, ir.Module)
        Verifier().verify(ir_module)

        # Try to parse ast as well:
        f = io.StringIO(src)
        tree = self.builder._create_ast(src, None)
        printer = CPrinter()
        print(tree)
        printer.print(tree)

    def expect_errors(self, src, errors):
        with self.assertRaises(CompilerError) as cm:
            self.do(src)
        for row, message in errors:
            self.assertEqual(row, cm.exception.loc.row)
            self.assertRegex(cm.exception.msg, message)

    def test_hello_world(self):
        src = r"""
        void printf(char*, ...);
        void main(int b) {
          printf("Hello \x81 world %i\n", 42);
        }
        """
        self.do(src)

    def test_adjecent_strings(self):
        src = r"""
        void printf(char*);
        void main(int b) {
          printf("Hello" "world\n");
          static unsigned char msg[]= "Woooot\n";
          printf(msg);
        }
        """
        self.do(src)

    def test_1(self):
        src = """
        int a;
        void main(int b) {
         a = 10 + b;
        }
        """
        self.do(src)

    def test_2(self):
        src = """
        static int c, d, e;
        static float x;
        char f, g;
        int main() {
          int d;
          d = 20 + c * 10 + c >> 2 - 123;
          return d;
        }
        """
        self.do(src)

    def test_control_structures(self):
        src = """
        int main() {
          int d,i,c;
          c = 2;
          d = 20 + c * 10 + c >> 2 - 123;
          if (d < 10)
          {
            while (d < 20)
            {
              d = d + c * 4;
            }
          }

          if (d > 20)
          {
            do {
              d += c;
            } while (d < 100);
          }
          else
          {
            for (i=i;i<10;i++) { }
            for (i=0;;) { }
            for (;;) { }
          }
          return d;
        }
        """
        self.do(src)

    def test_conditionals(self):
        src = """
        int main() {
          int d, i, c;
          c = (( (d < 10) || (i != c) ) | 22) != 0;
          return c;
        }
        """
        self.do(src)

    def test_expressions(self):
        """ Test various expression constructions """
        src = """
        void main() {
          int a,b,c,d;
          c = 2;
          d = a + b - c / a * b;
          d = !a;
          d = a ? b : c + 2;
        }
        """
        self.do(src)

    def test_4(self):
        """ Test expressions """
        src = """
        int main(int, int c) {
          int stack[2];
          struct { int ptr;} *s;
          int d;
          d = 20 + c * 10 + c >> 2 - 123;
          d = stack[--s->ptr];
          --d;
          d--;
          return d;
        }
        """
        self.do(src)

    def test_5(self):
        src = """
        static int G;
        void initialize(int g)
        {
          G = g;
        }
        int main(int, int c) {
          int d = 2;
          initialize(d);
          return d;
        }
        """
        self.do(src)

    def test_type_modifiers(self):
        """ Test the various constructs of type names """
        src = """
        void main() {
        int n;
        n = sizeof(int);
        int *a[3];
        n = sizeof(int *[3]);
        int (*p)[3];
        n = sizeof(int (*)[3]);
        n = sizeof(int *(void));
        volatile const int * volatile vc;
        }
        int *f(void);
        """
        self.do(src)

    def test_struct(self):
        """ Test structure usage """
        src = """
        typedef struct {int quot, rem; } div_t;
        struct z { int foo; };
        struct s;
        struct s* p;
        struct s {
         struct s *next;
         int b:2+5, c:9, d;
         struct z Z;
         int *g;
        };
        struct s AllocS;
        void main() {
         volatile div_t x, *y;
         x.rem = 2;
         y = &x;
         y->quot = x.rem = sizeof *AllocS.g;
         struct s S;
         S.next->next->b = 1;
        }
        """
        self.do(src)

    def test_union(self):
        """ Test union usage """
        src = """
        union z { int foo; struct { int b, a, r; } bar;};
        union z myZ[2] = {1, 2, 3};
        void main() {
          union z localZ[2] = {1, 2, 3};
        }
        """
        self.do(src)

    def test_array(self):
        """ Test array types """
        src = """
        int a[10];
        int b[] = {1, 2};
        int bbb[] = {1, 2,}; // Trailing comma
        void main() {
         int c[sizeof(long int)/sizeof(char)];
         unsigned long long d[] = {1ULL, 2ULL};
         a[2] = b[10] + c[2] + d[1];
         int* p = a + 2;
         int A[][3] = {1,2,3,4,5,6,7,8,9};
        }
        """
        self.do(src)

    def test_array_index_pointer(self):
        """ Test array indexing of a pointer type """
        src = """
        void main() {
         int* a, b;
         b = a[100];
        }
        """
        self.do(src)

    def test_size_outside_struct(self):
        """ Assert error when using bitsize indicator outside struct """
        src = """
         int b:2+5, c:9, d;
        """
        self.expect_errors(src, [(2, 'Expected ";"')])

    def test_wrong_tag_kind(self):
        """ Assert error when using wrong tag kind """
        src = """
        union S { int x;};
        int B = sizeof(struct S);
        """
        self.expect_errors(src, [(3, 'Wrong tag kind')])

    def test_enum(self):
        """ Test enum usage """
        src = """
        void main() {
         enum E { A, B, C=A+10 };
         enum E e = A;
         e = B;
         e = 2;
        }
        """
        self.do(src)

    def test_literal_data(self):
        """ Test various formats of literal data """
        src = """
        void main() {
         int i;
         char *s, c;
         i = 10l;
         s = "Hello!" "World!";
         c = ' ';
        }
        """
        self.do(src)

    def test_assignment_operators(self):
        """ Test assignment operators """
        src = """
        void main() {
         int a, b, c;
         a += b - c;
         a -= b - c;
         a /= b - c;
         a %= b - c;
         a |= b - c;
         a &= b - c;
        }
        """
        self.do(src)

    def test_sizeof(self):
        """ Test sizeof usage """
        src = """
        void main() {
         int x, *y;
         union U;
         union U { int x; };
         union U u;
         x = sizeof(float*);
         x = sizeof *y;
         x = sizeof(*y);
         x = sizeof(union U);
         int w = sizeof w;  // Sizeof works on the expression before the '='
        }
        """
        self.do(src)

    def test_goto(self):
        """ Test goto statements """
        src = """
        void main() {
          goto part2;
          part2: goto part2;
          switch(0) {
           case 34: break;
           default: break;
          }
        }
        """
        self.do(src)

    def test_continue(self):
        """ Test continue statement """
        src = """
        void main() {
          while (1) {
            continue;
          }
        }
        """
        self.do(src)

    def test_break(self):
        """ Test break statement """
        src = """
        void main() {
          while (1) {
            break;
          }
        }
        """
        self.do(src)

    def test_switch(self):
        """ Test switch statement """
        src = """
        void main() {
          int a;
          short b = 23L;
          switch (b) {
            case 34:
              a -= 5;
              break;
            case 342LL:
              break;
            default:
              a += 2;
              break;
          }
        }
        """
        self.do(src)

    def test_loose_case(self):
        """ Test loose case statement """
        src = """
        void main() {
          case 34: break;
        }
        """
        self.expect_errors(src, [(3, 'Case statement outside')])

    def test_loose_default(self):
        """ Test loose default statement """
        src = """
        void main() {
          default: break;
        }
        """
        self.expect_errors(src, [(3, 'Default statement outside')])

    def test_void_function(self):
        """ Test calling of a void function """
        src = """
        void main(void) {
          main();
        }
        """
        self.do(src)

    def test_function_arguments(self):
        """ Test calling of functions """
        src = """
        void add(int a, int b, int c);
        void main() {
          add((int)22, 2, 3);
        }
        """
        self.do(src)

    def test_forward_declaration(self):
        """ Test forward declarations """
        src = """
        extern char a;
        char a = 2;
        """
        self.do(src)

    def test_softfloat_bug(self):
        """ Bug encountered in softfloat library """
        src = """
        #define INLINE
        typedef short int16;
        typedef unsigned int bits32;
        typedef char int8;

        INLINE void
         shift64ExtraRightJamming(
             bits32 a0,
             bits32 a1,
             bits32 a2,
             int16 count,
             bits32 *z0Ptr,
             bits32 *z1Ptr,
             bits32 *z2Ptr
         )
        {
            bits32 z0, z1, z2;
            int8 negCount = ( - count ) & 31;

            if ( count == 0 ) {
                z2 = a2;
                z1 = a1;
                z0 = a0;
            }
            else {
                if ( count < 32 ) {
                    z2 = a1<<negCount;
                    z1 = ( a0<<negCount ) | ( a1>>count );
                    z0 = a0>>count;
                }
                else {
                    if ( count == 32 ) {
                        z2 = a1;
                        z1 = a0;
                    }
                    else {
                        a2 |= a1;
                        if ( count < 64 ) {
                            z2 = a0<<negCount;
                            z1 = a0>>( count & 31 );
                        }
                        else {
                            z2 = ( count == 64 ) ? a0 : ( a0 != 0 );
                            z1 = 0;
                        }
                    }
                    z0 = 0;
                }
                z2 |= ( a2 != 0 );
            }
            *z2Ptr = z2;
            *z1Ptr = z1;
            *z0Ptr = z0;

        }
        """
        self.do(src)

    def test_initialization(self):
        """ Test calling of functions """
        src = """
        char x = '\2';
        int* ptr = (int*)0x1000;

        void main() {
          char x = '\2';
          int* ptr = (int*)0x1000;
        }
        """
        self.do(src)

    def test_function_pointer_passing(self):
        """ Test passing of function pointers """
        src = """

        void callback(void)
        {
        }

        static void (*cb)(void);
        void register_callback(void (*f)())
        {
          cb = f;
        }

        void main() {
          register_callback(callback);
        }
        """
        self.do(src)


class CSynthesizerTestCase(unittest.TestCase):
    @unittest.skip('todo')
    def test_hello(self):
        """ Convert C to Ir, and then this IR to C """
        src = r"""
        void printf(char*);
        void main(int b) {
          printf("Hello" "world\n");
        }
        """
        builder = CBuilder(ExampleArch(), COptions())
        f = io.StringIO(src)
        try:
            ir_module = builder.build(f, None)
        except CompilerError as compiler_error:
            lines = src.split('\n')
            compiler_error.render(lines)
            raise
        assert isinstance(ir_module, ir.Module)
        Verifier().verify(ir_module)
        synthesizer = CSynthesizer()
        synthesizer.syn_module(ir_module)


if __name__ == '__main__':
    unittest.main()
