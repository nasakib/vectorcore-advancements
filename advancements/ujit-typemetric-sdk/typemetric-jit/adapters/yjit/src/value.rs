//! Ruby VALUE Type Tag Mapping Layer for Typemetric
//! 
//! Translates CRuby's immediate and heap VALUE tags into discrete 8-bit metric type IDs.

#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum RubyValType {
    Unknown = 0,
    Nil = 1,
    True = 2,
    False = 3,
    Fixnum = 4,
    Flonum = 5,
    StaticSymbol = 6,
    String = 7,
    Array = 8,
    Hash = 9,
    HeapObject = 10,
}

impl RubyValType {
    /// Inspects a raw CRuby 64-bit VALUE and extracts its classification tag.
    #[inline(always)]
    pub fn from_raw_value(val: usize) -> Self {
        // CRuby tag encoding:
        // LSB 1 = Fixnum (val & 0x01 != 0)
        // 0x02 = Flonum (val & 0x02 != 0 in modern CRuby, or special mask)
        // 0x04 = Static Symbol
        // 0x00 = False, 0x08 = Nil, 0x14 = True
        if (val & 0x01) != 0 {
            return RubyValType::Fixnum;
        }
        if val == 0x00 {
            return RubyValType::False;
        }
        if val == 0x08 {
            return RubyValType::Nil;
        }
        if val == 0x14 {
            return RubyValType::True;
        }
        if (val & 0x0e) == 0x0c {
            return RubyValType::StaticSymbol;
        }
        if (val & 0x03) == 0x02 {
            return RubyValType::Flonum;
        }
        // Otherwise heap pointer
        RubyValType::HeapObject
    }

    #[inline(always)]
    pub fn as_type_id(self) -> u8 {
        self as u8
    }
}
